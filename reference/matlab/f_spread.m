classdef f_spread
    methods(Static)
        
        function [brands,brand_gen] =...
            f_brand_gen(grid_size, rows, columns, binary_cover,...
            fire, fstep, lstep,...
            wind_s, wind_d, fb_wind_coef, fb_wind_sd, fb_wind_sd_transverse,...
            fb_veg_gen, fb_str_ig, veg_included, tstep, domains_mat)

            brands = double.empty(2,0);
            brand_gen = zeros(rows, columns);
            
            for ki = 1:rows
                for kj = 1:columns
                    if binary_cover(ki,kj) > 0
                        if fire(ki,kj) >= fstep
                            if fire(ki,kj) <= lstep
                                brand_gen(ki,kj) = round( (306.77*exp(0.1879*wind_s(ki,kj,tstep)))* (grid_size*2*sqrt((grid_size/2)^2+1)) /(lstep-fstep+1) );
                            end
                        end
                    end
                end
            end
                  

%             brand_gen(binary_cover > 0 & fire >= fstep & fire <= lstep) =...
%                 round( (306.77*exp(0.1879*wind_s(:,:,tstep)))* (grid_size*2*sqrt((grid_size/2)^2+1)) /(lstep-fstep+1) );
           
            brand_gen(binary_cover < 0 & veg_included & fire >= 1 & fire < 2 & domains_mat ~= 9) = fb_veg_gen;

            for i=1:rows
                for j=1:columns

                    nb = brand_gen(i,j);

                    if nb ~= 0
                        % longitudinal direction of transport [m]
                        dforward = lognrnd( log(fb_wind_coef*wind_s(i,j,tstep)), fb_wind_sd, 1, nb); %mean=6
                        % transversal direction of transport [m]
                        dlateral = normrnd(0, fb_wind_sd_transverse, 1, nb);

                        % project brands transport to x and y coordinates [m]
                        % direction zero means rightward (Eastward), so 270 means Southward for example.
                        dispy = - dforward.*sind(wind_d(i,j,tstep)) + dlateral.*cosd(wind_d(i,j,tstep)); % y is positive downward
                        dispx = dforward.*cosd(wind_d(i,j,tstep))   + dlateral.*sind(wind_d(i,j,tstep)); % x is positive rightward

                        % convert brands transport to number of cells
                        ynum = fix( dispy/grid_size + sign(dispy) ); % # rows 
                        xnum = fix( dispx/grid_size + sign(dispx) ); % # columns

                        % make sure brands are in the domain
                        deposit_y = (ynum+i >= 1).*(ynum+i <= rows).*(ynum+i);
                        deposit_x = (xnum+j >= 1).*(xnum+j <= columns).*(xnum+j);

                        nonzeros_x = deposit_x~=0;
                        nonzeros_y = deposit_y~=0;
                        nonzeros_xy = nonzeros_x .* nonzeros_y;

                        deposit_x = deposit_x(nonzeros_xy~=0);
                        deposit_y = deposit_y(nonzeros_xy~=0);

                        % update matrices
                        [counts_brands, index_brands] = groupcounts( sub2ind([rows,columns],deposit_y,deposit_x)' );
                        % for the following conditional, remember that
                        % min(fb_str_ig,fb_veg_ig) should be used.
                        brands = [ brands [index_brands(counts_brands>=fb_str_ig)';counts_brands(counts_brands>=fb_str_ig)'] ];
                    end

                end%for j
            end%for i
        end
        
        function radtotal =...
            f_radiation_gen(grid_size, rows, columns,binary_cover,...
            fire, tmpr, radtotal, fstep, lstep, rad_rf,...
            wind_d, aes, ee, er, sconst, tstep)

            p = repmat(1:1:columns, rows, 1);
            q = repmat([1:1:rows]', 1, columns);

            for i=1:rows
                for j=1:columns

                    if binary_cover(i,j) > 0
                        % radiation works when fully developed
                        if fire(i,j)*binary_cover(i,j) >= fstep && fire(i,j)*binary_cover(i,j) <= lstep
                            rx = p - j;
                            ry = q - i;
                            angle_correction = [ [repmat(180, rows, j-1)] [[zeros(i, columns-j+1)];[repmat(360, rows-i, columns-j+1)]] ];
                            angle = -atand(ry./rx);
                            rangle = angle + angle_correction; % angles in same convention as unit circle (trigonometry)

                            r2 = ( (grid_size*rx).^2 + (grid_size*ry).^2 ) .* (rangle >= wind_d(i,j,tstep)-90) .* (rangle <= wind_d(i,j,tstep)+90);
                            configfactor = zeros(rows,columns);
                            configfactor(r2~=0) = aes ./ ( pi * r2(r2~=0) );
                            emissivity = 1 / ((1/ee)+(1/er)-1);
                            radflux = configfactor * emissivity * sconst * ( ((tmpr(fix(fire(i,j)))+273.15)^4) - (293.15^4) );
                            radflux(isnan(radflux)) = 0;
                            radtotal= radflux + rad_rf * radtotal;
                            %energycounter = energycounter + radflux;
                        end%if fire
                    end%if homes

                end%for j
            end%for i
        end
        
        function ignition =...
            f_radiation_ig(ignition, binary_cover, radtotal, rad_energy_ig, criteria_rad, limrad)

            ignition(binary_cover>0 & ignition==0 & radtotal>rad_energy_ig & criteria_rad<=limrad) = 1;

        end
        
        function ignition =...
            f_brand_ig(grid_size, rows, columns, binary_cover, ignition, fileID,...
            brands, fb_str_ig, fb_veg_ig, fb_dist_mu, fb_dist_sd, veg_included,...
            domains_mat, criteria_spo, limspo)
            
            speeder = unique(brands(1,:));

            for i=1:rows
                for j=1:columns

                    if binary_cover(i,j) > 0 && ignition(i,j) == 0 && criteria_spo(i,j) <= limspo
            
                        if ismember(sub2ind([rows columns], i, j),speeder)
                            ind = sub2ind([rows columns], i, j);
                            
                            % ignition in structures
                            if any(brands(2,brands(1,:)==ind) >= fb_str_ig, 'All')
        
                                x_start = random('Uniform',0,grid_size,[1,sum(brands(1,:)==ind)]);
                                Xz = cell2mat( arrayfun( @(begin,L) begin+random('Lognormal',fb_dist_mu,fb_dist_sd,[1,L]), x_start, brands(2,brands(1,:)==ind), 'uni', false ) );
                                % there are two stripes each of which with width of 0.1 [m]
                                Yz = cell2mat( arrayfun( @(L) random('Uniform',0,0.2,[1,L]), brands(2,brands(1,:)==ind), 'uni', false ) );
                                %stripe 1
                                max_num_brand_1 = 0;
                                if ~isempty([Xz(Yz<0.1);Yz(Yz<0.1)])
                                    % 0.05 is radius of the circle from Santamaria paper
                                    max_num_brand_1 = max( cellfun('size', rangesearch([Xz(Yz<0.1);Yz(Yz<0.1)]',[Xz(Yz<0.1);Yz(Yz<0.1)]', 0.05), 2) );
                                    if max_num_brand_1 >= fb_str_ig
                                        ignition(i,j) = 1;
                                    end
                                end
                                %stripe 2
                                max_num_brand_2 = 0;
                                if ~isempty([Xz(Yz>=0.1);Yz(Yz>=0.1)])
                                    max_num_brand_2 = max( cellfun('size', rangesearch([Xz(Yz<0.1);Yz(Yz<0.1)]',[Xz(Yz<0.1);Yz(Yz<0.1)]', 0.05), 2) );
                                    if max_num_brand_2 >= fb_str_ig
                                        ignition(i,j) = 1;
                                    end
                                end
        
                                max_num_brand = max(max_num_brand_1, max_num_brand_2);
        
                                fprintf(fileID, ['Number of brands land on the pixel(' num2str(i) ',' num2str(j) '): ' num2str(length(Xz)) newline]);
                                fprintf(fileID, ['Max number of brands in a Santamaria circle: ' num2str(max_num_brand) newline]);
                                %disp(['number of brands land on the pixel: ' num2str(length(Xz))])
                                %disp(['max number of brands in a circle: ' num2str(max_num_brand)])
                            end
                        end
                    end
                    
                    % ignition in vegetation
                    if veg_included && binary_cover(i,j) < 0 && ignition(i,j) == 0 && domains_mat(i,j) < 8
                        ind = sub2ind([rows columns], i, j);
                        if sum(brands(2,brands(1,:)==ind)) >= fb_veg_ig 
                            ignition(i,j) = 1; 
                            %fclose(report_name);
                        end
                    end
                end%for j
            end%for i 
        end
    end    
end