#!/bin/sh

echo "Starting Caddy with authentication setup..."

# Default credentials if not provided by Railway
AUTH_USERNAME=${AUTH_USERNAME:-admin}
AUTH_PASSWORD=${AUTH_PASSWORD:-changeme}

echo "Generating password hash for user: $AUTH_USERNAME"

# Generate bcrypt hash for the password
PASSWORD_HASH=$(htpasswd -bnBC 12 "" "$AUTH_PASSWORD" | cut -d: -f2)

# Create the auth configuration file
cat > /etc/caddy/generated/auth.caddy << EOF
# Basic authentication configuration
# Generated automatically from environment variables
basic_auth {
	$AUTH_USERNAME $PASSWORD_HASH
}
EOF

echo "Authentication configured for user: $AUTH_USERNAME"
echo "Password hash generated and stored"

# Validate Caddyfile before starting
echo "Validating Caddy configuration..."
caddy validate --config /etc/caddy/Caddyfile

if [ $? -eq 0 ]; then
	echo "Configuration valid, starting Caddy server..."
	exec caddy run --config /etc/caddy/Caddyfile
else
	echo "Configuration validation failed, exiting..."
	exit 1
fi