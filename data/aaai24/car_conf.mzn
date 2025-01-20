enum TYPE = { city, limo, xdrive};
enum FUEL = {four, six, ten};

var TYPE: v_type;
var FUEL: v_fuel;
var bool: v_skibag;
var bool: v_wheel;

% c1: 4-wheel = yes ⇒ type = xdrive
constraint v_wheel == true -> v_type == TYPE[xdrive];

% c2: skibag =yes -> type!=city
constraint v_skibag == true -> v_type != TYPE[city];

% c3: fuel=4l⇒type=city
constraint v_fuel == FUEL[four] -> v_type == TYPE[city];

% c4: fuel = 6l -> type != xdrive
constraint v_fuel == FUEL[six] -> v_type != TYPE[xdrive];

% c5: type == city -> fuel != 10l
constraint v_type == TYPE[city] -> v_fuel != FUEL[ten];

% not(tv1): not(type = city ∧ fuel = 10l)
constraint v_type != TYPE[city] \/ v_fuel != FUEL[ten];

% not(tv2): not(type = city ∧ fuel = 6l)
constraint v_type != TYPE[city] \/ v_fuel != FUEL[six];

% t1: skibag = yes ∧ type = city
% constraint v_skibag == true /\ v_type = TYPE[city];
% t2: fuel = 6l
% constraint v_fuel == FUEL[six];
% t3: 4_wheel = yes ∧ fuel = 6l
constraint v_wheel == true /\ v_fuel = FUEL[six];

solve satisfy;

output ["type=\(v_type)\t fuel=\(v_fuel)\t",
           "skibag=\(v_skibag)\t wheel=\(v_wheel)\n"];