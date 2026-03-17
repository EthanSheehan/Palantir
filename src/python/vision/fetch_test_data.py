import os

import structlog

logger = structlog.get_logger()


def provide_test_data_links():
    """Logs links to industry-standard drone datasets."""
    logger.info("drone_test_datasets", datasets=[
        {"name": "VisDrone-Dataset", "desc": "High density vehicle tracking", "link": "http://aiskyeye.com/download/visdrone-2019-dataset/"},
        {"name": "UAV123", "desc": "Long-term aerial tracking", "link": "https://cvlab.hku.hk/projects/uav123/"},
        {"name": "YouTube High Density", "link": "https://www.youtube.com/watch?v=MNn9q9uiLpU"},
        {"name": "YouTube Single Object", "link": "https://www.youtube.com/watch?v=V-XN31hGcl8"},
    ])
    logger.info("usage_hint", msg="Download as .mp4 and update 'vision_processor.py' source.")

if __name__ == "__main__":
    provide_test_data_links()
