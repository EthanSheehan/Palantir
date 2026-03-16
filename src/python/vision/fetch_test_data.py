import os

def provide_test_data_links():
    """Prints links to industry-standard drone datasets."""
    print("--- Project Antigravity: Drone Test Datasets ---")
    print("1. VisDrone-Dataset (High density vehicle tracking)")
    print("   Link: http://aiskyeye.com/download/visdrone-2019-dataset/")
    print("2. UAV123 (Long-term aerial tracking)")
    print("   Link: https://cvlab.hku.hk/projects/uav123/")
    print("3. YouTube Test Clips (Direct MP4 download recommended for simulation):")
    print("   - High Density: https://www.youtube.com/watch?v=MNn9q9uiLpU")
    print("   - Single Object Tracking: https://www.youtube.com/watch?v=V-XN31hGcl8")
    print("\nTo use these for simulation, download as .mp4 and update 'vision_processor.py' source.")

if __name__ == "__main__":
    provide_test_data_links()
