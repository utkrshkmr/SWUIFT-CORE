% This code is the main body of SWUIFT model.
% All input files and functions are located in the same directory as this file.

%%
clc
clear
close all

load('default_values.mat');

community = 'Eaton';
report_name = 'Eaton_sim01';
t_start_vec = [2025,01,07,18,20,0];
t_end_vec = [2025,01,08,14,20,0];
grid_size = 10;
clear u
clear udir
clear ugust

load('wind_eaton.mat');
load('eaton_inputs_all.mat')
load("fire_prog.mat");
load("domains_mat.mat");

%In this case, the only known ignitions come from the WRF-FIRE simulation
knownig_mat = fire_prog;
clear fire_prog

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%The following code creates a vector that tracks (1) ignition occurrence,
%(2) ignition cause, and (3) ignition timestep
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
zvector = zeros(max(homes_mat, [], 'all'),5);
for temp1 = 1:max(homes_mat, [], 'all')
    zvector(temp1,1) = temp1;
end
clear temp1
%column 1 tracks building number
%column 2 tracks ignition
%column 3 tracks ignition caused by thermal radiation
%column 4 tracks ignition caused by fire spotting
%column 5 tracks timestep at ignition
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

rng(123456)

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%The following code introduces structure hardening capabilities
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

%Level of hardening in % for each mode of fire spread
hardening_level_rad = 70;
hardening_level_spo = 70;

limrad = 1 - (hardening_level_rad / 100); 
limspo = 1 - (hardening_level_spo / 100); 

mat_1_rad = zeros(size(lati,1), size(long,1));
mat_1_spo = zeros(size(lati,1), size(long,1));

% %This is a temporal solution to avoid ignition of category 3 buildings
% binary_cover(hardening_mat == 3) = 0;
% homes_mat(hardening_mat == 3) = 0;

%Extract the homes_mat values only for hardened structures
mat_1_rad(binary_cover == 1 & hardening_mat_rad ~= 1) = homes_mat(binary_cover == 1 & hardening_mat_rad ~= 1); 
mat_1_spo(binary_cover == 1 & hardening_mat_spo ~= 1) = homes_mat(binary_cover == 1 & hardening_mat_spo ~= 1);

%Extract unique home numbers for hardened structures
vector_1_rad = unique(mat_1_rad);
vector_1_spo = unique(mat_1_spo);

%Remove the first value which is equal to zero
vector_1_rad(1) = [];
vector_1_spo(1) = [];

%Create a negative vector that counts how many hardened structures there are
vector_2_rad = zeros(size(vector_1_rad, 1),1);
vector_2_spo = zeros(size(vector_1_spo, 1),1);
for i = 1:size(vector_1_rad, 1)
	vector_2_rad(i) = -i;
end
for i = 1:size(vector_1_spo, 1)
	vector_2_spo(i) = -i;
end

%Create a matrix with all homes numbered and replace hardened homes' with negative values starting from -1
mat_2_rad = zeros(size(lati,1), size(long,1));
mat_2_spo = zeros(size(lati,1), size(long,1));
mat_2_rad(binary_cover == 1) = homes_mat(binary_cover == 1);
mat_2_spo(binary_cover == 1) = homes_mat(binary_cover == 1);
for i = 1:size(vector_1_rad, 1)
	mat_2_rad(mat_2_rad == vector_1_rad(i)) = vector_2_rad(i);
end
for i = 1:size(vector_1_spo, 1)
	mat_2_spo(mat_2_spo == vector_1_spo(i)) = vector_2_spo(i);
end

%Create matrices to store the ignition criteria based on random values and the input levels of hardening
criteria_rad = zeros(size(lati,1), size(long,1));
criteria_spo = criteria_rad;
for t = 1:size(vector_1_rad, 1)
	temp_rand_rad = rand;
	criteria_rad(mat_2_rad == -t) = temp_rand_rad;
end
for t = 1:size(vector_1_spo, 1)
	temp_rand_spo = rand;
	criteria_spo(mat_2_spo == -t) = temp_rand_spo;
end

%For cases where 3-domain solution is used, adjust probability of ignition of structures located outside the community domain
criteria_ave = (criteria_rad + criteria_spo) / 2;
limave = (limspo + limrad) / 2;
knownig_mat(mat_2_spo < 0 & criteria_ave > limave) = 0;
knownig_mat(mat_2_rad < 0 & criteria_ave > limave) = 0;

clear t temp_rand_rad temp_rand_spo mat_1_rad mat_1_spo mat_2_rad mat_2_spo vector_1_rad vector_1_spo vector_2_rad vector_2_spo criteria_ave limave
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%The following section of code is exclusively for the creation of a csv
%file that can be exported to ArcGIS
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
arcgis_lat_start = 1;
arcgis_lat_total = numel(lati);
arcgis_long_start = 1;
arcgis_long_total = numel(long);

arcgis_rows = arcgis_lat_total;
arcgis_columns = arcgis_long_total;
arcgis_class = 0;

arcgis_fire_97 = zeros(arcgis_rows,arcgis_columns);

arcgis_binary_cover = zeros(arcgis_rows,arcgis_columns);
for i = 1:arcgis_rows
    for j = 1: arcgis_columns
        arcgis_binary_cover(i,j) = binary_cover(i+arcgis_lat_start-1,j+arcgis_long_start-1);
    end
end

arcgis_lati = zeros(arcgis_lat_total,1);
for i = 1:arcgis_rows
    arcgis_lati(i,1) = lati(i+arcgis_lat_start-1,1);
end

arcgis_long = zeros(arcgis_long_total,1);
for i = 1:arcgis_columns
    arcgis_long(i,1) = long(i+arcgis_long_start-1,1);
end

clear i j 
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
mkdir('outs')

%% preparation
% times when steps take place:
t_num_vec = datenum(t_start_vec):t_step_min/60/24:datenum(t_end_vec);
% limits of time-steps for radiation and brand generation
% (fully developed fire, 22 & 177 are based on OZone)
fstep = fix(22/t_step_min)+1; %first time-step
lstep = fix(177/t_step_min)+1; %last time-step

fb_str_ig = ceil(24/fb_mass); % criterion for structure ignition, due to branding, based on Santamaria paper




%%%%%%%
% This changed to account for new grid size 
fb_veg_gen = ceil( ((grid_size*grid_size) / (2.25 * pi / 4)) * (87 / fb_mass) ); % brand generation from a vegetation cell, based on Wickramasinghe paper (yellow cover)
%%%%%%%





fb_veg_ig = 64 * ceil(3.5/fb_mass) + 1; % criterion for vegetation ignition, based on Suzuki(2020) paper and pigeonhole principle
maxstep = length(t_num_vec); % # of steps of the analysis

% determine the size of the matrices to be created, based on input rasters
rows = size(binary_cover,1);
columns = size(binary_cover,2);

% create fire matrices
ignition = zeros(rows,columns);
fire = zeros(rows,columns);
% create matrix to count brands landed in each cell
% brandcounter = zeros(rows,columns,rows*columns);
% create matrix for total registered radiant exposure
radtotal = zeros(rows,columns);

%%%%%%%
%April 24: create matrix to store earliest time of cells on fire
out_fire = zeros(rows,columns);
%%%%%%%

% tracking ignitions
ig_known = zeros(maxstep,1);
ig_dev   = zeros(maxstep,1);
ig_rad   = zeros(maxstep,1);
ig_brand = zeros(maxstep,1);
ig_total = zeros(maxstep,1);

house_ig_known = zeros(maxstep,1);
house_ig_rad = zeros(maxstep,1);
house_ig_brand = zeros(maxstep,1);
house_ig_total = zeros(maxstep,1);

% for the spread .gif file
im = cell(maxstep,1);


% documentation
fopen([cd '\outs\' report_name '.txt'],'w');
fileID = fopen([cd '\outs\' report_name '.txt'],'a');
dt1 = datestr( datetime(now, 'ConvertFrom', 'datenum') );
fprintf(fileID,...
    [newline, 'Spread loop begins at: ', dt1, newline,...
    '################################' newline]);
fprintf(fileID, [newline, 'grid cell size = ', num2str(grid_size), ' m', newline]);
fprintf(fileID, [newline, 'start time = ', datestr(datenum(t_start_vec),'yyyy/mm/dd HH:MM'), newline]);
fprintf(fileID, [newline, 'end time = ', datestr(datenum(t_end_vec),'yyyy/mm/dd HH:MM'), newline]);
fprintf(fileID, [newline, 'time step = ', num2str(t_step_min), ' minutes', newline]);
fprintf(fileID, [newline, 'When ignited, a structure is in fully developed phase between time steps ', num2str(fstep), ' and ', num2str(lstep), newline]);
fprintf(fileID, [newline, 'threshold for ignition due to radiation = ', num2str(rad_energy_ig), ' [W/m2]', newline]);
fprintf(fileID, [newline, 'emissivity of the receiving surface = ', num2str(er), newline]);
fprintf(fileID, [newline, 'emissivity of the emitting surface = ', num2str(ee), newline]);
fprintf(fileID, [newline, 'area for radiating surface = ', num2str(aes), ' m2', newline]);
fprintf(fileID, [newline, 'radiation reduction factor = ', num2str(rad_rf), newline]);
%fprintf(fileID, [newline, 'peak distance for lognormal brand transport = ', num2str(brand_peak_dist), ' m', newline]);
fprintf(fileID, [newline, 'mass of each firebrand = ', num2str(fb_mass), ' g', newline]);
fprintf(fileID, [newline, 'number of brands for Santamaria condition = ', num2str(fb_str_ig), newline]);
fprintf(fileID, [newline, 'number of brands for igniting vegetation = ', num2str(fb_veg_ig), newline]);
fprintf(fileID, [newline, 'number of brands generated from vegetation = ', num2str(fb_veg_gen), newline]);
fprintf(fileID, [newline, '################################']);


%% spread
rng(10)
for tstep=1:maxstep

    fprintf(fileID, [newline 'We are at the moment ' datestr(datenum(t_num_vec(tstep)),'yyyy/mm/dd HH:MM') newline]);
    
%    brandcounter = zeros(rows,columns,rows*columns);
    
    % increment one stage for the burning fires
    fire(fire > 0) = fire(fire > 0) + 1;
    
    %Incorporate known ignitions from wildfire



    
    %%%%%%%
    % This changed to prevent FARSITE ignitions inside the urban domain:
    ignition(knownig_mat == tstep & domains_mat >= 8) = 1;
    %%%%%%%





    %disp(['Total number of pixels ignited so far: ' num2str( sum(ignition,'All') )])



    %%%%%%%
    % This changed because known ignitions for this case can only take place for wildland and transition domains:
    ig_known(tstep) = sum( ignition(homes_mat > 0 & knownig_mat == tstep & domains_mat >= 8),'All');
    %%%%%%%
    
    
    
    
    
    
    ig_tmp = sum( ignition(homes_mat > 0),'All');




    %%%%%%%
    % This changed accordingly to ig_known:
    house_ig_known(tstep) = length(unique(homes_mat(homes_mat > 0 & knownig_mat == tstep & domains_mat >= 8)));
    %%%%%%%





    house_ig_tmp = length(unique(homes_mat(homes_mat > 0 & ignition == 1)));
    fprintf(fileID, ['- Known ignitions (if any) are registered.' newline]);
    fprintf(fileID, ['    Total number of structure pixels ignited so far: ', num2str(ig_tmp) newline]);
    fprintf(fileID, ['    Total number of structures ignited so far: ', num2str(house_ig_tmp) newline]);
    
    % Igniting rest of the house if one of its pixels gets fully developed
    fprintf(fileID, ['- Igniting rest of the house if one of its pixels gets fully developed.' newline]);
    Ind = ignition==1 & binary_cover>0;
    homes_id = nonzeros(unique(homes_mat(Ind)));
    for i=1:length(homes_id)
        Ind = find(homes_mat==homes_id(i));
        if any( fire(Ind) >= fstep, 'All' )
            ignition(Ind)=1;
        end
    end
    ig_dev(tstep) = sum( ignition(homes_mat > 0),'All') - ig_tmp;
    ig_tmp = sum( ignition(homes_mat > 0),'All');
    fprintf(fileID, ['    Total number of structure pixels ignited so far: ' num2str(ig_tmp)  newline]);
    

    % obtain a wind speed by probability
%     windprob = rand;
%     if windprob >= 0.8
%         wind_s = ugust(tstep);
%     else
%         wind_s = u(tstep);
%     end
%     wind_d = udir(tstep);
    
    
    % BRANDING
    [brands,brand_gen] = f_spread.f_brand_gen(grid_size, rows, columns, binary_cover,...
        fire, fstep, lstep,...
        wind_s, wind_d, fb_wind_coef, fb_wind_sd, fb_wind_sd_transverse,...
        fb_veg_gen, fb_str_ig, veg_included, tstep, domains_mat);

    fprintf(fileID, ['- Brands are generated and transported.' newline]);
    %disp('Brands are generated and transported.')
    
    
    % RADIATION
    radtotal = f_spread.f_radiation_gen(grid_size, rows, columns, binary_cover,...
        fire, tmpr, radtotal, fstep, lstep, rad_rf,...
        wind_d, aes, ee, er, sconst, tstep);

    fprintf(fileID, ['- Radiation fluxes from fully developed pixels are evaluated.' newline]);
    
    
    % IGNITION DUE TO RADIATION
    % radiation only ignites structures
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    dummyig = ignition;
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

    ignition = f_spread.f_radiation_ig(ignition, binary_cover, radtotal, rad_energy_ig, criteria_rad, limrad);
    
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    %Update the zvector with new ignitions%
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    for i=1:rows
        for j=1:columns
            if dummyig(i,j) ~= ignition(i,j)
                if binary_cover(i,j) > 0
                    if zvector(homes_mat(i,j),2) == 0
                        zvector(homes_mat(i,j),2) = 1;
                        zvector(homes_mat(i,j),3) = 1;
                        zvector(homes_mat(i,j),5) = tstep;
                    end
                end
            end
        end
    end   
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

    fprintf(fileID, ['- Ignitions due to RADIATION (if any) are registered.' newline]);
    ig_rad(tstep) = sum(ignition(homes_mat > 0),'All') - ig_tmp;
    ig_tmp = sum(ignition(homes_mat > 0),'All');
    house_ig_rad(tstep) = length(unique(homes_mat(homes_mat > 0 & ignition == 1))) - house_ig_tmp;
    house_ig_tmp = length(unique(homes_mat(homes_mat > 0 & ignition == 1)));
    fprintf(fileID, ['    Total number of structure pixels ignited so far: ' num2str(ig_tmp)  newline]);
    fprintf(fileID, ['    Total number of structures ignited so far: ' num2str(house_ig_tmp)  newline]);
    
    
    % IGNITION DUE TO BRANDING
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    dummyig = ignition;
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

    ignition = f_spread.f_brand_ig(grid_size, rows, columns, binary_cover, ignition, fileID,...
    brands, fb_str_ig, fb_veg_ig, fb_dist_mu, fb_dist_sd, veg_included, domains_mat,...
    criteria_spo, limspo);

    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    %Update the zvector with new ignitions%
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    for i=1:rows
        for j=1:columns
            if dummyig(i,j) ~= ignition(i,j)
                if binary_cover(i,j) > 0
                    if zvector(homes_mat(i,j),2) == 0
                        zvector(homes_mat(i,j),2) = 1;
                        zvector(homes_mat(i,j),4) = 1;
                        zvector(homes_mat(i,j),5) = tstep;
                    end
                end
            end
        end
    end   
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

    fprintf(fileID, ['- Ignitions due to BRANDING (if any) are registered.' newline]);
    ig_brand(tstep) = sum(ignition(homes_mat > 0),'All') - ig_tmp;
    ig_tmp = sum(ignition(homes_mat > 0),'All');
    house_ig_brand(tstep) = length(unique(homes_mat(homes_mat > 0 & ignition == 1))) - house_ig_tmp;
    house_ig_tmp = length(unique(homes_mat(homes_mat > 0 & ignition == 1)));
    fprintf(fileID, ['    Total number of structure pixels ignited so far: ' num2str( sum(ignition(homes_mat > 0),'All') )  newline]);
    fprintf(fileID, ['    Total number of structurs ignited so far: ' num2str(house_ig_tmp)  newline]);
    fprintf(fileID, ['    The time at this point is: ', datestr( datetime(now, 'ConvertFrom', 'datenum') ),  newline]);
        
    % Register new fires into the fire matrix
    for i=1:rows
        for j=1:columns
           if fire(i,j) == 0 && ignition(i,j) == 1
                   fire(i,j) = 0.11;
           end
        end
    end
    ig_total(tstep) = sum(ignition(homes_mat > 0),'All');
    house_ig_total(tstep) = length(unique(homes_mat(homes_mat > 0 & ignition == 1)));
    
    im = f_plots.f_snapshots(rows, columns, binary_cover, ignition, fire,...
        long, lati, t_num_vec, tstep, fstep, lstep, im, water);


    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    %The following code generates a list of fire points to be exported to ArcGIS
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    if tstep == 97
        fopen([cd '\outs\97.txt'],'w');
        IDarcgis97 = fopen([cd '\outs\97.txt'],'a');
        fprintf(IDarcgis97, ['LON,LAT,CLASS', newline]);
        for i = 1:arcgis_rows
            for j = 1: arcgis_columns
                arcgis_fire_97(i,j) = fire(i+arcgis_lat_start-1,j+arcgis_long_start-1);
                if arcgis_fire_97(i,j) > 0
                    if arcgis_binary_cover(i,j) == -1
                        arcgis_class = 1;
                    elseif arcgis_binary_cover(i,j) == 1
                        arcgis_class = 2;
                    else
                        arcgis_class = 0;
                    end
                    fprintf(IDarcgis97, [num2str(arcgis_long(j)), ',', num2str(arcgis_lati(i)), ',', num2str(arcgis_class), newline]);
                end
            end
        end
        fclose(IDarcgis97);
    end
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    
    %%%%%%%%%%%
    %%%%%%%%%%%
    %April 24: track earliest occurrence of fires:
    for wi = 1:rows
        for ji = 1:columns
            if fire(wi,ji) ~= 0
                if out_fire(wi,ji) == 0
                    out_fire(wi,ji) = (tstep - 1) * 5;
                end
            end
        end
    end
    clear wi ji
    %%%%%%%%%%%
    %%%%%%%%%%%

end% for time step

dt2 = datestr( datetime(now, 'ConvertFrom', 'datenum') );
fprintf(fileID,...
    [newline, '################################', newline,...
    'Runtime is about ', num2str(round((datenum(dt2)-datenum(dt1))*24*60)), ' minutes.', newline]);

%%%%%%%%%%%
%April 24: remove "0" cells that were never reached by the fire
for wi = 1:rows
    for ji = 1:columns
        if out_fire(wi,ji) == 0
            if knownig_mat(wi,ji) == 0
                out_fire(wi,ji) = "";
            end
        end
    end
end
clear wi ji
%%%%%%%%%%%

%% Creating the gif
f_plots.f_gif(report_name, im, fileID);

%% Creating pixel ignition plot
f_plots.f_plot_pix_ig(report_name, maxstep, t_num_vec, fileID,...
    ig_known, ig_dev, ig_rad, ig_brand, ig_total);

%% Creating structure ignition plot
f_plots.f_plot_str_ig(report_name, maxstep, t_num_vec, fileID,...
    house_ig_known, house_ig_rad, house_ig_brand, house_ig_total);

%%
clear dummyig wind_d wind_s
save([cd '\outs\' report_name '_vars.mat'], '-v7.3')
fprintf(fileID, [newline 'Variables from workspace are saved.'  newline]);

%%%%%%%%%%%%%%%%%%%%%%%%%%
%%% Probabilistic code %%%
%%%%%%%%%%%%%%%%%%%%%%%%%%
fprintf(fileID,...
    [newline, '################################', newline,...
    'rad_energy_ig: ', num2str(rad_energy_ig), newline,...
    'fb_wind_coef: ', num2str(fb_wind_coef), newline,...
    'fb_wind_sd: ', num2str(fb_wind_sd), newline,...
    'fb_wind_sd_transverse: ', num2str(fb_wind_sd_transverse), newline,...
    'fb_mass: ', num2str(fb_mass), newline,...
    'fb_dist_mu: ', num2str(fb_dist_mu), newline,...
    'fb_dist_sd: ', num2str(fb_dist_sd), newline]);
%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%

fclose(fileID);

%% Save fire progression output into a csv text file
csvwrite([cd '\outs\fire_prog.txt'], out_fire);
%save zvector to an excel file
xlswrite([cd '\outs\zvector.xlsx'],zvector);