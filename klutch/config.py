import argparse


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--debug", help="Debug mode", action="store_true",
    )
    parser.add_argument(
        "--dry-run", help="Do not change anything", action="store_true",
    )
    parser.add_argument(
        "--namespace",
        help="Namespace to operate in (only required when running out of cluster)",
    )
    return parser.parse_args()
