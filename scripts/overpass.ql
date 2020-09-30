Alpine Huts:

[out:json][timeout:25][bbox:{{bbox}}];
(
way["tourism"="alpine_hut"];
node["tourism"="alpine_hut"];
);
out center;
{{style:
node{
  text: eval('tag("name")');
}
}}


Lift w/o stations:

[out:json][timeout:25][bbox:{{bbox}}];
way["aerialway"]["aerialway"!="magic_carpet"] -> .lifts;
foreach.lifts -> .l {
  node(w.l)[!"aerialway"];
  out;
}


Short lifts with names:

[out:json][timeout:25][bbox:{{bbox}}];
way["aerialway"](if: length () < 500) -> .lifts;
node(w.lifts)["aerialway"="station"]["name"];
out;


Hiking routes:

[out:json][timeout:25][bbox:{{bbox}}];
relation["route"="hiking"]["ref"="7"];
out body;
>;
out skel qt;


Lifts no piste:

[out:json][timeout:25][bbox:{{bbox}}];
way["piste:type"] -> .p;
(
  node["aerialway"="station"]; - node(w.p);
);
out;


Unconnected parkings:

[out:json][timeout:25][bbox:{{bbox}}];

(
way["amenity"="parking"];
node["amenity"="parking"];
) -> .parkings;

way["highway"] -> .highways;
node (w.highways) -> .hn;

foreach .parkings -> .p (
  (
    node (w.p);
    .p;
  ) -> .pn;
  node.pn.hn -> .n;

  if (n.count (nodes) < 1) {
    .p out center;
  }
);
