classdef f_plots
    methods(Static)
        
        function im = f_snapshots(rows, columns, binary_cover, ignition, fire,...
            long, lati, t_num_vec, tstep, fstep, lstep, im, water)
            % fig1: animation of the spread (.gif)
            fig1 = figure('color','w','unit','inch','position',[1 1 8 8], 'Visible',false);
            set(0,'defaultaxesfontsize',18);

            % order in values, pix_status and cmap matters, as they correspond to each other
            values = [-5 -4 -2 -1 0 1 2 3 4];
            pix_status = ["water", "veg burned", "veg ignited", "veg", "not-combustible",...
                "str", "str ignited", "str developed", "str burned"];
            cmap = [0.67 0.8 0.91 %water
                0 0.3 0 %veg_burned
                1 1 0 %veg_ignited
                0.54 .64 0.48 %veg
                0.7 0.7 0.7 %none-combustable
                0.44 0.5 0.56 %str
                1 0 0 %str_ignited
                0.55 0.13 0.32 %str_developed
                0 0 0.2 %str_burned
                ];

            % for annotation
            ant1 = []; ant2 = []; ant3 = [];

            % Snapshot of the spread
            plt_mat = zeros(rows,columns);
            plt_mat(binary_cover < 0) = -1; %veg
            plt_mat(binary_cover == 0) = 0; %none-combustable
            plt_mat(binary_cover > 0) = 1; %str
            plt_mat(ignition.*binary_cover < 0) = -2; %veg_ignited
            plt_mat(ignition.*binary_cover > 0) = 2; %str_ignited
            plt_mat(binary_cover > 0 & fire >= fstep & fire <= lstep) = 3; %str_developed
            plt_mat(binary_cover > 0 & fire > lstep) = 4; %str_burned
            plt_mat(binary_cover < 0 & fire > 1) = -4; %veg_burned
            plt_mat(water > 0) = -5; %veg

            [status ,idx] = intersect(values, unique(plt_mat));
            for cl = 1:length(status)
                plt_mat(plt_mat == status(cl)) = 100*cl;
            end

            hs = pcolor(long, lati, plt_mat);
            colormap(cmap(idx,:));
            set(hs, 'EdgeColor', 'none')
            cb = colorbar;
            set(gca, 'clim', [min(min(plt_mat))-50 max(max(plt_mat))+50]);
            set(cb, 'ticks', min(min(plt_mat)):100:max(max(plt_mat)), 'ticklabels', pix_status(idx));
            %title([community, ' ', datestr(datenum(t_num_vec(step)),'yyyy/mm/dd HH:MM')]);
            title([datestr(datenum(t_num_vec(tstep)),'HH:MM') ' MST']);

            frame = getframe(fig1);
            im{tstep} = frame2im(frame);

            fn_ig_foto = [cd '\outs\' num2str(tstep) '.png'];
            saveas(fig1, fn_ig_foto);

            close(fig1);

        end

        function f_gif(report_name, im, fileID)
            fn_spread = [cd '\outs\' report_name '.gif'];

            [A,map] = rgb2ind(im{1}, 256);  % actually, im{first counter of "step"}
            imwrite(A, map, fn_spread, 'gif', 'LoopCount', Inf, 'DelayTime', 1);
            for idx = 2:length(im)  % whatever the range of "step" is, starting from 2nd count 
                [A,map] = rgb2ind(im{idx}, 256);  % actually, im{first counter of "step"}
                imwrite(A, map, fn_spread, 'gif', 'WriteMode', 'append', 'DelayTime', 0.25);
            end

            fprintf(fileID, [newline 'Gif file of the spread is generated.' newline] );
        end

        function f_plot_pix_ig(report_name, maxstep, t_num_vec, fileID,...
            ig_known, ig_dev, ig_rad, ig_brand, ig_total)
            fn_ig_pixel = [cd '\outs\' report_name '_ig_pixel.png'];

            fig2 = figure('color','w','unit','inch','position',[1 1 8 7], 'Visible',false);
            set(0,'defaultaxesfontsize',18);
            plot(1:maxstep,cumsum(ig_known,1)', 'LineWidth', 2, 'Color', [1 0.7 0], 'DisplayName', 'Known');
            hold on
            plot(1:maxstep,cumsum(ig_dev,1)', 'LineWidth', 2, 'Color', 'g', 'DisplayName', 'Developed');
            hold on
            plot(1:maxstep,cumsum(ig_rad,1)', 'LineWidth', 2, 'Color', 'r', 'DisplayName', 'Radiation');
            hold on
            plot(1:maxstep,cumsum(ig_brand,1)', 'LineWidth', 2, 'Color', 'k', 'DisplayName', 'Branding');
            hold on
            plot(1:maxstep,ig_total', 'LineWidth', 2, 'Color', 'b', 'DisplayName', 'Total');
            hold off
            legend('Location', 'northwest');


            xticks(1:fix(maxstep/6):maxstep);
            xticklabels({datestr(datenum(t_num_vec(1:fix(maxstep/6):maxstep)),'HH:MM')});
            xlabel('Time', 'fontsize', 24);
            ylh = ylabel('Number of ignited pixels', 'fontsize', 24);
            ylh.Position(1) = ylh.Position(1) - 0.1;
            saveas(fig2, fn_ig_pixel);

            close(fig2);

            fprintf(fileID, [newline 'Plot for number of pixels ignitied is generated.' newline] );

        end

        function f_plot_str_ig(report_name, maxstep, t_num_vec, fileID,...
            house_ig_known, house_ig_rad, house_ig_brand, house_ig_total)
            fn_ig_house = [cd '\outs\' report_name '_ig_house.png'];

            fig3 = figure('color','w','unit','inch','position',[1 1 8 7], 'Visible',false);
            set(0,'defaultaxesfontsize',18);
            plot(1:maxstep,cumsum(house_ig_known,1)', 'LineWidth', 2, 'Color', [1 0.7 0], 'DisplayName', 'Known');
            hold on
            plot(1:maxstep,cumsum(house_ig_rad,1)', 'LineWidth', 2, 'Color', 'r', 'DisplayName', 'Radiation');
            hold on
            plot(1:maxstep,cumsum(house_ig_brand,1)', 'LineWidth', 2, 'Color', 'k', 'DisplayName', 'Branding');
            hold on
            plot(1:maxstep,house_ig_total', 'LineWidth', 2, 'Color', 'b', 'DisplayName', 'Total');
            hold off
            legend('Location', 'northwest');

            xticks(1:fix(maxstep/6):maxstep);
            xticklabels({datestr(datenum(t_num_vec(1:fix(maxstep/6):maxstep)),'HH:MM')});
            xlabel('Time', 'fontsize', 24);
            ylh = ylabel('Number of ignited structures', 'fontsize', 24);
            ylh.Position(1) = ylh.Position(1) - 0.1;
            saveas(fig3, fn_ig_house);

            close(fig3);

            fprintf(fileID, [newline 'Plot for number of structures ignitied is generated.' newline] );
        end     
    end
end