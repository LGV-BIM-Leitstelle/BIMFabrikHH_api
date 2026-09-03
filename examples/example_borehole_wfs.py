#!/usr/bin/env python3

from typing import Any, Dict
from lxml import etree
from time import perf_counter

from src.api.ogc_api.services.http_requests import DataFetcher, HamburgOGCAPI
from src.api.config import api_settings


# Small bounding box with 4 boreholes.
BBOX: Dict[str, float] = {
    "min_x": 9.9861, 
    "min_y": 53.4867, 
    "max_x": 9.9872, 
    "max_y": 53.4872
}

# Large bounding box with 750 boreholes.
# BBOX: Dict[str, float] = {
#     "min_x": 9.9700,
#     "min_y": 53.5461,
#     "max_x": 9.9922,
#     "max_y": 53.5561,
# }


NAMESPACES = {
    "wfs":  "http://www.opengis.net/wfs/2.0",
    "gml":  "http://www.opengis.net/gml/3.2",
    "bml":  "http://www.infogeo.de/boreholeml/3.0",
    "gmd":  "http://www.isotc211.org/2005/gmd",
    "gn":   "urn:x-inspire:specification:gmlas:GeographicalNames:3.0",
    "gco":  "http://www.isotc211.org/2005/gco",
}


def main():
    start_time = perf_counter()
    root = DataFetcher.fetch_borehole_data(BBOX)
    end_time = perf_counter()

    print(f"Ausführungszeit: {end_time - start_time} Sekunden")

    # Find all WFS members
    members = root.xpath(
        "//wfs:member",
        namespaces=NAMESPACES,
    )

    for member in members:
        borehole = member.xpath(
                "./bml:Borehole",
                namespaces=NAMESPACES)[0]

        borehole_id = borehole.xpath(
            "./bml:id/text()", 
            namespaces=NAMESPACES
            )[0]
        print(borehole_id)

        borehole_position = borehole.xpath(
            "./bml:location/gml:Point/gml:pos/text()", 
            namespaces=NAMESPACES
            )[0]
        print(borehole_position)

    print(f"The bounding box contains {len(members)} boreholes.")


if __name__ == "__main__":
    main()