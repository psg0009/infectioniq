"""
InfectionIQ Demo Script
Plays both videos sequentially: sanitized → skip sanitization → stops
Syncs events with backend for real-time dashboard updates
"""

import sys
import os
import httpx
import asyncio

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.main import CVPipeline

BACKEND_URL = "http://localhost:8000"


def get_active_case_id():
    """Get an active case ID from backend, or create one"""
    try:
        # Try to get active cases
        response = httpx.get(f"{BACKEND_URL}/api/v1/cases/", timeout=5.0)
        if response.status_code == 200:
            cases = response.json()
            if cases and len(cases) > 0:
                case_id = cases[0].get("id")
                print(f"  Using existing case: {case_id[:8]}...")
                return case_id
    except Exception as e:
        print(f"  Could not fetch cases: {e}")

    return None


def run_demo():
    """Run demo with both videos sequentially"""

    # Video files (resolve relative to this script's directory)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    videos = [
        (os.path.join(project_root, "sanatized.mp4"), "Compliant - Person Sanitizes"),
        (os.path.join(project_root, "skip santization.mp4"), "Non-Compliant - Person Skips Sanitizer")
    ]

    print("\n" + "="*60)
    print("  InfectionIQ Demo")
    print("  Press 'q' to skip to next video, or wait for it to end")
    print("="*60)

    # Get case ID for backend sync
    print("\n  Connecting to backend...")
    case_id = get_active_case_id()
    if case_id:
        print(f"  Backend connected! Events will sync to dashboard.")
    else:
        print(f"  Running in offline mode (no backend sync)")

    print("="*60 + "\n")

    for i, (video_path, description) in enumerate(videos, 1):
        print(f"\n[{i}/{len(videos)}] Now playing: {description}")
        print(f"    File: {video_path}")
        print("-"*50)

        pipeline = CVPipeline(
            video_path=video_path,
            backend_url=BACKEND_URL,
            case_id=case_id,
            loop_video=False  # Don't loop - play once and move to next
        )

        pipeline.run()

        print(f"[{i}/{len(videos)}] Finished: {description}\n")

    print("\n" + "="*60)
    print("  Demo Complete!")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_demo()
