#!/usr/bin/env python3
"""
Latency measurement script for app init endpoints
Measures GET /patients, GET /patient-status, GET /checklist
"""
import time
import requests
import statistics
import sys

API_BASE = "http://127.0.0.1:8000/api/v1"
DEVICE_ID = "latency-test-device"
NUM_ITERATIONS = 10


def measure_endpoint(name: str, url: str, headers: dict):
    """Measure latency for a single endpoint"""
    times = []
    errors = 0
    
    print(f"\nMeasuring {name}...")
    
    for i in range(NUM_ITERATIONS):
        start = time.time()
        try:
            response = requests.get(url, headers=headers, timeout=5)
            duration = (time.time() - start) * 1000  # Convert to ms
            times.append(duration)
            if response.status_code != 200:
                errors += 1
                print(f"  Iteration {i+1}: {response.status_code} - {duration:.2f}ms")
            else:
                print(f"  Iteration {i+1}: {duration:.2f}ms")
        except Exception as e:
            errors += 1
            duration = (time.time() - start) * 1000
            print(f"  Iteration {i+1}: ERROR - {e} ({duration:.2f}ms)")
    
    if times:
        avg = statistics.mean(times)
        median = statistics.median(times)
        min_time = min(times)
        max_time = max(times)
        p95 = statistics.quantiles(times, n=20)[18] if len(times) > 1 else times[0]
        
        print(f"\n  Results for {name}:")
        print(f"    Average: {avg:.2f}ms")
        print(f"    Median:  {median:.2f}ms")
        print(f"    Min:     {min_time:.2f}ms")
        print(f"    Max:     {max_time:.2f}ms")
        print(f"    P95:     {p95:.2f}ms")
        print(f"    Errors:  {errors}/{NUM_ITERATIONS}")
        return {
            'name': name,
            'avg': avg,
            'median': median,
            'min': min_time,
            'max': max_time,
            'p95': p95,
            'errors': errors
        }
    else:
        print(f"  ERROR: All requests failed for {name}")
        return None


def main():
    """Run latency measurements"""
    headers = {
        'X-Device-ID': DEVICE_ID,
        'Content-Type': 'application/json'
    }
    
    # First, create a patient if it doesn't exist
    print("Setting up test patient...")
    try:
        patient_response = requests.post(
            f"{API_BASE}/patients",
            headers=headers,
            json={
                "name": "Latency Test Patient",
                "email": "test@example.com",
                "date_of_birth": "1980-01-01",
                "has_ckd_esrd": True,
                "last_gfr": 45,
                "has_referral": True
            },
            timeout=5
        )
        if patient_response.status_code in [200, 201]:
            print("✅ Test patient created")
        else:
            print(f"⚠️  Patient creation returned {patient_response.status_code}")
    except Exception as e:
        print(f"⚠️  Could not create test patient: {e}")
        print("   Continuing with measurements anyway...")
    
    # Wait a moment for status/checklist to be precomputed
    time.sleep(0.5)
    
    # Measure endpoints
    results = []
    
    result = measure_endpoint(
        "GET /api/v1/patients",
        f"{API_BASE}/patients",
        headers
    )
    if result:
        results.append(result)
    
    result = measure_endpoint(
        "GET /api/v1/patient-status",
        f"{API_BASE}/patient-status",
        headers
    )
    if result:
        results.append(result)
    
    result = measure_endpoint(
        "GET /api/v1/checklist",
        f"{API_BASE}/checklist",
        headers
    )
    if result:
        results.append(result)
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    if results:
        total_avg = sum(r['avg'] for r in results) / len(results)
        print(f"\nAverage latency across all endpoints: {total_avg:.2f}ms")
        print("\nPer-endpoint averages:")
        for r in results:
            print(f"  {r['name']:30} {r['avg']:7.2f}ms (median: {r['median']:.2f}ms)")
    else:
        print("No successful measurements")
        sys.exit(1)


if __name__ == "__main__":
    main()
