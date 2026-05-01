# Quick Start on Windows

This guide is for Git Bash on Windows. If you're on macOS/Linux, the commands
are mostly the same but paths use forward slashes.

## Prerequisites

You already have:
- ✅ Python 3.10+ installed
- ✅ AWS account ready
- ✅ Red Hat pull secret downloaded
- ✅ Claude API key

You need to install:
- `openshift-install` binary (required for actual cluster deployment)
- `aws` CLI (required for pre-flight checks and IPI)
- `oc` CLI (required for cluster management)

### Install openshift-install and oc (one-time)

Download both from
<https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest/>

For Windows:

```bash
# From Git Bash, create a tools folder in your home dir
mkdir -p ~/ocp-tools
cd ~/ocp-tools

# Download the installer for Windows
curl -LO https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest/openshift-install-windows.zip
unzip openshift-install-windows.zip
# This gives you openshift-install.exe

# Download the oc client for Windows
curl -LO https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest/openshift-client-windows.zip
unzip openshift-client-windows.zip
# This gives you oc.exe

# Add ~/ocp-tools to your PATH permanently
echo 'export PATH="$HOME/ocp-tools:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Verify
openshift-install.exe version
oc.exe version --client
```

### Install AWS CLI (one-time)

Download from <https://awscli.amazonaws.com/AWSCLIV2.msi> — install using the
MSI (it auto-adds to PATH).

Then in Git Bash:

```bash
aws --version       # should print aws-cli/2.x
aws configure       # enter your access key, secret, region, output format
aws sts get-caller-identity   # should print your account info
```

## Install the OCP Agent tool

```bash
# From Git Bash, wherever you want to keep the tool
cd ~
unzip ocp-agent-tool.zip -d ocp-agent-tool
cd ocp-agent-tool

# Create a virtual environment (recommended but optional)
python -m venv .venv
source .venv/Scripts/activate  # note: /Scripts/ on Windows, not /bin/

# Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Create your config file
cp .env.example .env

# Edit .env — fill in your Claude API key and AWS region
# Use your favorite editor. Notepad works:
notepad .env

# Save your pull secret in the expected location (or update .env)
mkdir -p ~/.ocp-agent
cp ~/Downloads/pull-secret.json ~/.ocp-agent/pull-secret.json
```

## Run it

### Web UI (recommended first run)

```bash
python run.py --web
```

Open <http://localhost:8765> in your browser.

### Terminal UI (for power users)

```bash
python run.py --cli
```

## Try it out

Whichever interface you chose, start with something safe:

```
You: Run pre-flight checks: validate my AWS credentials, region ap-south-1, and a Route53 zone for ocp.cloudnestinfoworks.com
```

The agent will:
1. Call `check_aws` (no confirmation needed — it's read-only)
2. Report what it found
3. Tell you what's ready and what needs fixing

Once that's green, try:

```
You: Deploy a new OpenShift 4.15 cluster on AWS in ap-south-1 with cluster name "meeru-dev", base domain "ocp.cloudnestinfoworks.com", 2 workers of type m5.large
```

The agent will:
1. Ask any remaining questions (pull secret path confirmation, etc.)
2. Generate the install-config.yaml
3. Ask you to confirm writing the file
4. Ask you to confirm running `openshift-install create cluster` (this is the ~45 min step)
5. Stream the installer output as it progresses

## Troubleshooting

### "ANTHROPIC_API_KEY is not set"

Edit `.env` and paste your Claude API key from <https://console.anthropic.com/settings/keys>

### "openshift-install: command not found"

Make sure `~/ocp-tools` is in your PATH. Check with `echo $PATH`.

### "No AWS credentials found"

Run `aws configure` in Git Bash. Verify with `aws sts get-caller-identity`.

### Web UI won't load

- Check the terminal where you ran `python run.py --web` for errors
- Port 8765 might be in use — use `python run.py --web --port 9090`
- Windows firewall might be blocking — it'll prompt you on first run, click "Allow"

### "ModuleNotFoundError: anthropic" (or any other module)

Your virtualenv isn't activated, or dependencies weren't installed. Run:

```bash
source .venv/Scripts/activate
pip install -r requirements.txt
```

### Slow response from Claude

First response of a session can take 10-20 seconds as Claude builds context.
Subsequent responses are faster. Use the `--cli` mode if you want to see
what's happening in real-time (no waiting for full response).
