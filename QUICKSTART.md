# Windows Quick Start — 30 minutes from zip to working tool

Follow these steps in order. Don't skip ahead.

## Prerequisite checklist

Before starting, confirm you have:

- [ ] **Python 3.10+** installed (check: `python --version` in Git Bash)
- [ ] **Claude API key** from https://console.anthropic.com/settings/keys
- [ ] **Billing enabled** on Anthropic console (get $5 free credit)
- [ ] **Spending cap set** to $20/month at https://console.anthropic.com/settings/limits

If any are missing, handle those first.

## Step 1: Extract the tool (2 min)

Download `ocp-agent-tool.zip` and extract it somewhere permanent.
I recommend `~/ocp-agent-tool/` (your home folder).

In Git Bash:

```bash
cd ~
unzip ~/Downloads/ocp-agent-tool.zip
cd ocp-agent-tool
ls
# Should see: run.py, verify_api.py, README.md, ocp_agent/, tools/, web/, docs/
```

## Step 2: Create Python virtual environment (3 min)

A virtualenv keeps the tool's dependencies separate from any other Python projects.

```bash
# Still in ~/ocp-agent-tool

python -m venv .venv

# Activate it (Windows syntax — note /Scripts/ not /bin/)
source .venv/Scripts/activate

# Your prompt should now show (.venv) at the front, like:
# (.venv) Raj Prajapati@Meeraj_PC MINGW64 ~/ocp-agent-tool $
```

**Important:** Every time you open a new Git Bash terminal to run the tool, you need to activate the venv again with `source .venv/Scripts/activate`. Otherwise Python won't find the installed packages.

## Step 3: Install dependencies (5 min)

```bash
# Verify you're in the venv (prompt should show (.venv))
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

You'll see a lot of output. It ends with something like:
```
Successfully installed anthropic-0.40.0 flask-3.0.3 ...
```

If you see any "ERROR" lines in red, paste them so I can debug. A few "WARNING" lines about deprecation are fine and expected.

## Step 4: Configure your API key (2 min)

```bash
# Create your config file from the template
cp .env.example .env

# Edit it
notepad .env
```

In the file that opens, find this line:
```
ANTHROPIC_API_KEY=sk-ant-api03-...
```

Replace `sk-ant-api03-...` with your actual key (starts with `sk-ant-api03-` followed by a long string).

Save and close Notepad.

## Step 5: Verify API connectivity (1 min)

```bash
python verify_api.py
```

You should see:
```
  OCP Agent — API connectivity check
  ────────────────────────────────────────
  ✓ API key found (sk-ant-api03-...)
  ✓ Using model: claude-sonnet-4-20250514
  → Calling Claude API...
  ← Claude responded: OCP Agent API test OK

  ✓ All good! You can now run:
     python run.py --web   (for web UI)
     python run.py --cli   (for terminal UI)
```

**If you see errors here, STOP** — fix the API key or billing setup before trying to run the main tool. The error messages from `verify_api.py` tell you what to fix.

## Step 6: Launch the tool (30 seconds)

```bash
python run.py --web
```

You'll see:
```
  OCP Agent web UI → http://localhost:8765

  (Press Ctrl+C to stop)
```

Open **http://localhost:8765** in your browser.

You should see the same dark-themed UI as the demo, but now this one runs locally and can execute commands on your machine.

## Step 7: First real test (1 min)

In the web UI, type:

```
Run "whoami" and show me the output
```

You should see:
1. An orange confirmation card appears showing the command `whoami`
2. Click **"Approve & run"**
3. A blue box shows the output — something like `meeraj_pc\raj prajapati`

**If this works, you have a fully functional AI agent on your laptop.** Everything else is just adding more capabilities (AWS, OCP tools) for it to use.

## Step 8: Install the CLI tools you'll need for real work

These aren't needed for the agent itself — only for when you ask it to deploy clusters.

### AWS CLI (required for `check_aws` tool)

Download: https://awscli.amazonaws.com/AWSCLIV2.msi

Run the MSI. It auto-adds to PATH.

Close and reopen Git Bash, then:
```bash
aws --version
aws configure   # Enter your AWS access key + secret
aws sts get-caller-identity   # Should print your account
```

### `openshift-install` and `oc` CLI

In Git Bash:

```bash
mkdir -p ~/ocp-tools
cd ~/ocp-tools

curl -LO https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest/openshift-install-windows.zip
curl -LO https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest/openshift-client-windows.zip

unzip openshift-install-windows.zip
unzip openshift-client-windows.zip

# Add to PATH permanently
echo 'export PATH="$HOME/ocp-tools:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Verify
openshift-install.exe version
oc.exe version --client
```

### Red Hat pull secret

1. Go to https://console.redhat.com/openshift/install/aws/installer-provisioned
2. Click "Copy pull secret" or download as `pull-secret.txt`
3. Save it:

```bash
mkdir -p ~/.ocp-agent
# Copy the file from Downloads to ~/.ocp-agent/pull-secret.json
# Or paste the JSON content into a new file
```

## Step 9: Real workflow test

Back in the web UI:

```
Run pre-flight checks for an OpenShift deployment:
validate AWS credentials, region ap-south-1, 
and check if there's a Route53 public zone for ocp.cloudnestinfoworks.com
```

The agent will:
1. Run `check_aws` automatically (no confirmation — it's read-only)
2. Report green/red on each check
3. Tell you exactly what's ready and what needs fixing

Congrats — you now have an AI copilot that can actually deploy OpenShift clusters.

## Troubleshooting

### "python is not recognized"

Python isn't in your PATH. Reinstall Python and check "Add python.exe to PATH" during install.

### "source: command not found" in step 2

You're using Command Prompt, not Git Bash. Open Git Bash (installed with Git for Windows) and retry.

### "ANTHROPIC_API_KEY is not set"

`.env` file wasn't created or key wasn't saved. Run `cat .env | head -3` to see what's in there.

### `pip install` fails with SSL errors

Your corporate network might be intercepting. Try:
```bash
python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
```

### "Port 8765 already in use"

Something else is using port 8765. Use a different one:
```bash
python run.py --web --port 9090
```

### Web UI loads but chat doesn't respond

Check the terminal where `python run.py --web` is running — API errors print there. Most likely: API key issue or billing not set up.

### I closed the terminal and can't start the tool again

You need to reactivate the virtualenv every new terminal:
```bash
cd ~/ocp-agent-tool
source .venv/Scripts/activate
python run.py --web
```
