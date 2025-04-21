from request_oaf import HamburgOGCAPI

if __name__ == "__main__":
    import pandas as pd

    pd.set_option("display.max_rows", None)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", None)
    pd.set_option("display.max_colwidth", None)

    api = HamburgOGCAPI()

    # Bounding Box for Hamburg Area
    bbox = {
        "min_x": 9.9733,
        "min_y": 53.5544,
        "max_x": 9.9756,
        "max_y": 53.5556,
    }

    # API Parameters
    params_trees = {
        "f": "json",
        "bbox": f"{bbox['min_x']},{bbox['min_y']},{bbox['max_x']},{bbox['max_y']}",
        "crs": "http://www.opengis.net/def/crs/EPSG/0/25832",
    }

    # Fetch Trees Data
    base_url_trees = "https://api.hamburg.de/datasets/v1/strassenbaumkataster/collections/strassenbaumkataster/items"
    trees_data = api.fetch_data(base_url_trees, params_trees)
    # pprint(trees_data, width=400, sort_dicts=False)

    trees_df = api.data_to_dataframe(trees_data) if trees_data else None
    # print("\nStreet Trees DataFrame:")
    # print(trees_df)
    params_stadtmodell = {
        "f": "cityjson",
        "bbox": f"{bbox['min_x']},{bbox['min_y']},{bbox['max_x']},{bbox['max_y']}",
    }
    print(trees_df)
