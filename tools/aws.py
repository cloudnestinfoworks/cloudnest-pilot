"""AWS environment checks.

Read-only tool. Confirms the user's AWS setup is ready for an OCP install.
"""
from __future__ import annotations

from .registry import tool


@tool(
    name="check_aws",
    description=(
        "Validate the user's AWS environment is ready for OpenShift "
        "installation. Checks: (1) AWS credentials are configured and "
        "valid, (2) the specified region is available, (3) a public "
        "Route53 hosted zone exists for the requested base domain, "
        "(4) service quotas for VPC and EC2 instances look reasonable. "
        "Read-only — makes no changes to AWS."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "region": {
                "type": "string",
                "description": "AWS region, e.g. us-east-1 or ap-south-1",
            },
            "base_domain": {
                "type": "string",
                "description": "The base DNS domain for the cluster, e.g. ocp.example.com. Must have a Route53 public hosted zone.",
            },
        },
        "required": ["region", "base_domain"],
    },
    requires_confirmation=False,
)
def check_aws(region: str, base_domain: str) -> str:
    # Import here so users without boto3 installed can still use tools that
    # don't need AWS. Gracefully reports the missing dep.
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
    except ImportError:
        return "boto3 is not installed. Run: pip install boto3"

    results: list[str] = []

    # 1. Credentials
    try:
        sts = boto3.client("sts", region_name=region)
        identity = sts.get_caller_identity()
        results.append(
            f"✓ AWS credentials valid. Account: {identity['Account']}, "
            f"ARN: {identity['Arn']}"
        )
    except NoCredentialsError:
        return "✗ No AWS credentials found. Run `aws configure` or set AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY."
    except ClientError as e:
        return f"✗ AWS credentials are invalid or lack permissions: {e}"
    except BotoCoreError as e:
        return f"✗ AWS client error: {e}"

    # 2. Region available
    try:
        ec2 = boto3.client("ec2", region_name=region)
        ec2.describe_regions(RegionNames=[region])
        results.append(f"✓ Region {region} is enabled on this account")
    except ClientError as e:
        return f"✗ Region {region} is not available or not enabled: {e}"

    # 3. Route53 zone
    try:
        r53 = boto3.client("route53")
        zones = r53.list_hosted_zones_by_name(DNSName=base_domain, MaxItems="10")
        matching = [
            z
            for z in zones.get("HostedZones", [])
            if z["Name"].rstrip(".") == base_domain.rstrip(".")
            and not z.get("Config", {}).get("PrivateZone", False)
        ]
        if matching:
            zid = matching[0]["Id"].split("/")[-1]
            results.append(
                f"✓ Route53 public zone for {base_domain} exists (ID: {zid})"
            )
        else:
            results.append(
                f"✗ No public Route53 hosted zone found for {base_domain}. "
                "You must create one and delegate the domain before installing."
            )
    except ClientError as e:
        results.append(f"! Could not check Route53 zones: {e}")

    # 4. Quota hints (not a hard check — IPI needs ~25 vCPUs for default)
    try:
        quota = boto3.client("service-quotas", region_name=region)
        # L-1216C47A = "Running On-Demand Standard (A, C, D, H, I, M, R, T, Z) instances"
        q = quota.get_service_quota(ServiceCode="ec2", QuotaCode="L-1216C47A")
        limit = int(q["Quota"]["Value"])
        if limit < 32:
            results.append(
                f"! EC2 on-demand vCPU quota is only {limit} in {region}. "
                "IPI default install needs ~24 vCPUs (3 masters × 4 + 3 workers × 4). "
                "Consider requesting a quota increase to 64+."
            )
        else:
            results.append(f"✓ EC2 vCPU quota in {region}: {limit} (plenty)")
    except (ClientError, KeyError):
        # Quotas API is flaky and not essential — silently skip.
        pass

    return "\n".join(results)
