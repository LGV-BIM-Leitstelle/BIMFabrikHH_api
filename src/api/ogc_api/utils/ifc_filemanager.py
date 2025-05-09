import datetime
import os


def save_ifc_file_on_server(ifc_bytes: bytes, prefix: str, job_id: str) -> tuple[str, str, str]:
    current_file = os.path.abspath(__file__)
    # navigate to 'src'
    src_dir = os.path.abspath(os.path.join(current_file, "..", "..", "..", "..", ".."))
    output_dir = os.path.join(src_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    filename = f"{prefix}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{job_id}.ifc"
    file_path = os.path.join(output_dir, filename)
    with open(file_path, "wb") as f:
        f.write(ifc_bytes)

    url_http = f"http://gv-srv-w00186:8084/output/{filename}"
    url_https = f"https://gv-srv-w00186:8088/output/{filename}"

    return filename, url_http, url_https
