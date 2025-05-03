import json
import time

import requests

# Base URL for the API
BASE_URL = "http://127.0.0.1:8003"  # Make sure this matches your API server


def print_response(response, label="Response"):
    """Pretty print a response"""
    print(f"\n=== {label} ===")
    print(f"Status Code: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")

    # Print the first part of the response content for debugging
    print(f"Raw content preview: {response.text[:500]}")

    # Try to parse as JSON if possible
    try:
        print(json.dumps(response.json(), indent=2))
    except json.JSONDecodeError:
        print("Response is not valid JSON")

    print("=" * (len(label) + 8))


def test_connection():
    """Test basic connection to the server"""
    print("\n🔍 Testing: Basic connection to API server")
    try:
        response = requests.get(BASE_URL, timeout=5)
        print(f"Connection successful: Status code {response.status_code}")
        return True
    except requests.exceptions.ConnectionError as e:
        print(f"⚠️ Connection failed: {e}")
        print(f"Please verify the API server is running at {BASE_URL}")
        return False
    except Exception as e:
        print(f"⚠️ Error: {e}")
        return False


def test_list_processes():
    """Test listing all available processes"""
    print("\n🔍 Testing: List all processes")
    try:
        response = requests.get(f"{BASE_URL}/processes", timeout=5)
        print_response(response)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"⚠️ Unexpected status code: {response.status_code}")
            return None
    except Exception as e:
        print(f"⚠️ Error: {e}")
        return None


def test_get_process(process_id):
    """Test getting details of a specific process"""
    print(f"\n🔍 Testing: Get process '{process_id}' details")
    try:
        response = requests.get(f"{BASE_URL}/processes/{process_id}", timeout=5)
        print_response(response)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"⚠️ Unexpected status code: {response.status_code}")
            return None
    except Exception as e:
        print(f"⚠️ Error: {e}")
        return None


def test_execute_get_trees():
    """Test executing the get-trees process"""
    print("\n🔍 Testing: Execute get-trees process")
    payload = {
        "bbox": [9.9733, 53.5544, 9.9756, 53.5556],
        "crs": "http://www.opengis.net/def/crs/EPSG/0/25832",
        "limit": 10,
        "skip_geometry": True,
    }

    try:
        response = requests.post(f"{BASE_URL}/processes/get-trees/execution", json=payload, timeout=5)
        print_response(response)

        if response.status_code == 201:
            try:
                job_id = response.json().get("id")
                return job_id
            except Exception as e:
                print(f"⚠️ Could not parse job ID: {e}")
                return None
        else:
            print(f"⚠️ Unexpected status code: {response.status_code}")
            return None
    except Exception as e:
        print(f"⚠️ Error: {e}")
        return None


def test_execute_generate_tree_model():
    """Test executing the generate-tree-model process"""
    print("\n🔍 Testing: Execute generate-tree-model process")
    payload = {"bbox": [9.9847, 53.5519, 9.9856, 53.5522], "level_of_geom": 1, "project_name": "TestProject"}

    try:
        response = requests.post(f"{BASE_URL}/processes/generate-tree-model/execution", json=payload, timeout=5)
        print_response(response)

        if response.status_code == 201:
            try:
                job_id = response.json().get("id")
                return job_id
            except Exception as e:
                print(f"⚠️ Could not parse job ID: {e}")
                return None
        else:
            print(f"⚠️ Unexpected status code: {response.status_code}")
            return None
    except Exception as e:
        print(f"⚠️ Error: {e}")
        return None


def test_get_job_status(process_id, job_id):
    """Test getting the status of a job"""
    print(f"\n🔍 Testing: Get job status for job '{job_id}'")
    try:
        response = requests.get(f"{BASE_URL}/processes/{process_id}/jobs/{job_id}", timeout=5)
        print_response(response)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"⚠️ Unexpected status code: {response.status_code}")
            return None
    except Exception as e:
        print(f"⚠️ Error: {e}")
        return None


def test_get_job_results(process_id, job_id):
    """Test getting the results of a job"""
    print(f"\n🔍 Testing: Get job results for job '{job_id}'")
    try:
        response = requests.get(f"{BASE_URL}/processes/{process_id}/jobs/{job_id}/results", timeout=5)

        # Handle different content types
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            print_response(response)
        else:
            print(f"\n=== Results for job '{job_id}' ===")
            print(f"Status Code: {response.status_code}")
            print(f"Content-Type: {content_type}")
            print(f"Content-Length: {len(response.content)} bytes")
            print(f"First 100 bytes (hex): {response.content[:100].hex()}")
            print("=" * 40)

        return response
    except Exception as e:
        print(f"⚠️ Error: {e}")
        return None


def poll_until_complete(process_id, job_id, max_tries=10, wait_seconds=1):
    """Poll a job until it completes or fails"""
    print(f"\n⏳ Polling job '{job_id}' until completion...")

    for i in range(max_tries):
        job_status = test_get_job_status(process_id, job_id)
        if not job_status:
            print("Could not get job status")
            return None

        status = job_status.get("status")

        if status in ["successful", "failed"]:
            print(f"Job completed with status: {status}")
            return job_status

        print(f"Job status: {status}, progress: {job_status.get('progress', 0)}% - waiting {wait_seconds}s...")
        time.sleep(wait_seconds)

    print("Maximum polling attempts reached!")
    return None


def run_all_tests():
    """Run all API tests"""
    print("🔬 Starting API Tests 🔬")

    # Test basic connection first
    if not test_connection():
        print("❌ Basic connection test failed. Make sure your API is running and accessible.")
        return

    # Test listing processes
    processes = test_list_processes()
    if not processes:
        print("❌ Could not list processes. Stopping tests.")
        return

    # Continue with other tests...
    test_get_process("get-trees")
    test_get_process("generate-tree-model")

    # Test executing get-trees process
    get_trees_job_id = test_execute_get_trees()
    if get_trees_job_id:
        # Poll until job completes
        poll_until_complete("get-trees", get_trees_job_id)
        # Get the results
        test_get_job_results("get-trees", get_trees_job_id)

    # Test executing generate-tree-model process
    model_job_id = test_execute_generate_tree_model()
    if model_job_id:
        # Poll until job completes
        poll_until_complete("generate-tree-model", model_job_id)
        # Get the results
        test_get_job_results("generate-tree-model", model_job_id)

    print("\n✅ API Tests Completed")


if __name__ == "__main__":
    get_trees_job_id = test_execute_get_trees()
    #
    # try:
    #     run_all_tests()
    # except KeyboardInterrupt:
    #     print("\n⚠️ Test interrupted by user")
    #     sys.exit(1)
    # except Exception as e:
    #     print(f"\n❌ Unexpected error: {e}")
    #     sys.exit(1)
