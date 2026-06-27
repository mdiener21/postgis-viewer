import hashlib
import re

def test_query_id_generation():
    sql = "SELECT * FROM sample_points"
    query_id = hashlib.md5(sql.encode()).hexdigest()
    assert query_id == hashlib.md5("SELECT * FROM sample_points".encode()).hexdigest()
    print("Query ID generation test passed")

def test_bbox_regex():
    extent_str = "BOX(-122.4 37.7,-122.3 37.8)"
    match = re.match(r"BOX\((.*) (.*),(.*) (.*)\)", extent_str)
    assert match is not None
    bbox = [float(x) for x in match.groups()]
    assert bbox == [-122.4, 37.7, -122.3, 37.8]
    print("BBox regex test passed")

if __name__ == "__main__":
    test_query_id_generation()
    test_bbox_regex()
