from app_transformer.transformer_citygml import CoordinateTransformer

coordinate_transformer = CoordinateTransformer("EPSG:4326", "EPSG:25832")
x, y, z = coordinate_transformer.transform_point(9.25, 52.36, 10.0)
print(x, y, z)
