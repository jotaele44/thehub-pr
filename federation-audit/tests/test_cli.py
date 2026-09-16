from federation_audit.cli import build_parser


def test_default_manifest_schema_exists():
    args = build_parser().parse_args(["validate-manifest", "manifest.json"])

    assert args.schema.is_file()
    assert args.schema.name == "repository-audit-manifest.schema.json"


def test_default_runtime_schema_exists():
    args = build_parser().parse_args(
        [
            "runtime-certify",
            "--workspace-root",
            "workspace",
            "--manifest",
            "manifest.json",
            "--topology",
            "topology.json",
            "--shadow-root",
            "shadow",
            "--output",
            "receipt.json",
        ]
    )

    assert args.schema.is_file()
    assert args.schema.name == "runtime-certification.schema.json"
