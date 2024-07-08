import logging
import json
import os
import base64
import zlib
import uuid
from datetime import datetime
from nested_lookup import nested_alter
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from modules.analyzers import ANALYZER


logger = logging.getLogger(__name__)


def store_file(out: str, domain: str, prefix: str, data: any, ext: str) -> dict:
    filename = f"{out}/{prefix}_{domain}_{uuid.uuid4()}.{ext}"
    with open(filename, "wb") as f:
        if ext == "png" or ext == "har":
            f.write(zlib.decompress(base64.b64decode(data)))
        elif ext == "json":
            f.write(json.dumps(data, indent=4).encode())
    return {"type": "reference", "data": {"filename": filename, "extension": ext}}


def parser() -> ArgumentParser:
    parser = ArgumentParser(
        description="worker cli",
        formatter_class=ArgumentDefaultsHelpFormatter
    )
    analysis_parser = parser.add_subparsers(dest="analysis", required=True)
    parser.add_argument(
        "--log-level",
        help="log level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO"
    )
    parser.add_argument(
        "--out",
        help="output directory",
        type=str,
        default=f"/tmp/{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}",
        metavar="<str>"
    )
    for analysis in ANALYZER:
        p = analysis_parser.add_parser(
            analysis,
            help=f"run {analysis}",
            formatter_class=ArgumentDefaultsHelpFormatter
        )
        p.add_argument("--domain", help="domain", type=str, required=True, metavar="<str>")
        p.add_argument("--config", help=f"config", type=str, required=True, metavar="<str>")
    return parser


def main():
    args = parser().parse_args()

    logger.info(f"Configuring log level: {args.log_level}")
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s:%(name)s:%(levelname)s:%(message)s"
    )

    logger.info(f"Loading config: {args.config}")
    with open(args.config, "r") as f:
        config = json.load(f)

    logger.info(f"Starting {args.analysis} for domain: {args.domain}")
    result = ANALYZER[args.analysis](args.domain, config).start()

    logger.info(f"Creating output directory: {args.out}")
    os.makedirs(args.out, exist_ok=True)

    logger.info(f"Storing files")
    nested_alter(result, "login_page_candidate_screenshot",
        lambda data: store_file(args.out, args.domain, "login-page-candidate-screenshot", data, "png"), in_place=True)
    nested_alter(result, "idp_screenshot",
        lambda data: store_file(args.out, args.domain, "idp-screenshot", data, "png"), in_place=True)
    nested_alter(result, "keyword_recognition_screenshot",
        lambda data: store_file(args.out, args.domain, "keyword-recognition-screenshot", data, "png"), in_place=True)
    nested_alter(result, "logo_recognition_screenshot",
        lambda data: store_file(args.out, args.domain, "logo-recognition-screenshot", data, "png"), in_place=True)
    nested_alter(result, "idp_har",
        lambda data: store_file(args.out, args.domain, "idp-har", data, "har"), in_place=True)
    nested_alter(result, "login_page_analysis_har",
        lambda data: store_file(args.out, args.domain, "login-page-analysis-har", data, "har"), in_place=True)
    nested_alter(result, "login_trace_screenshot",
        lambda data: store_file(args.out, args.domain, "login-trace-screenshot", data, "png"), in_place=True)
    nested_alter(result, "login_trace_har",
        lambda data: store_file(args.out, args.domain, "login-trace-har", data, "har"), in_place=True)
    nested_alter(result, "login_trace_storage_state",
        lambda data: store_file(args.out, args.domain, "login-trace-storage-state", data, "json"), in_place=True)

    logger.info(f"Saving config: {args.out}")
    with open(f"{args.out}/config.json", "w") as f:
        json.dump(config, f, indent=4)

    logger.info(f"Saving result: {args.out}")
    with open(f"{args.out}/result.json", "w") as f:
        json.dump(result, f, indent=4)


if __name__ == "__main__":
    main()
