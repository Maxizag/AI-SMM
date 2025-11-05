# Environment Setup

This directory needs access to the `.env` file from the project root.

## Setup Instructions

### On Linux/macOS:

Create a symbolic link to the root .env file:

```bash
cd infra
ln -sf ../.env .env
```

### On Windows:

Create a symbolic link (requires admin privileges):

```cmd
cd infra
mklink .env ..\.env
```

Or simply copy the file:

```cmd
cd infra
copy ..\.env .env
```

### Verify Setup:

```bash
# From infra/ directory
ls -la .env
# Should show a symlink pointing to ../.env

# Test Docker Compose can read it
docker compose config | grep -i "token"
```

## Note

The `.env` file is gitignored for security. Each developer must:
1. Copy `.env.example` to `.env` in project root
2. Add their API keys and tokens
3. Create symlink in `infra/` directory as shown above
