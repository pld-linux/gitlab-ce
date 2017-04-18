#!/bin/sh
#
# gitlab-ctl implementing similar commands as gitlab omnibus package does
#
set -e

auto_migrations_skip_file=/etc/gitlab/skip-auto-migrations

die() {
	cat >&2
	exit 1
}

notice() {
	echo "gitlab $*"
}

# Migrate the database (options: VERSION=x, VERBOSE=false, SCOPE=blog)
upgrade() {
	gitlab-rake db:migrate "$@"
}

# GitLab | Create a backup of the GitLab system
backup() {
	gitlab-rake gitlab:backup:create "$@"
}

# Run backup before package upgrade
# https://gitlab.com/gitlab-org/omnibus-gitlab/blob/8.17.5+ce.0/config/templates/package-scripts/preinst.erb#L10
preinst() {
	if [ -f $auto_migrations_skip_file ]; then
		notice "preinstall: Found $auto_migrations_skip_file, skipping auto backup..."
		return
	fi

	notice "preinstall: Automatically backing up only the GitLab SQL database (excluding everything else!)"

	if ! backup SKIP=repositories,uploads,builds,artifacts,lfs,registry,pages; then

		cat >&2 <<-EOF

		Backup failed! If you want to skip this backup, run the following command and try again:

		touch ${auto_migrations_skip_file}

		EOF
		exit 1
	fi
}

# Run migrations after a package upgrade
# https://gitlab.com/gitlab-org/omnibus-gitlab/blob/8.8.1+ce.0/config/templates/package-scripts/posttrans.erb
# https://gitlab.com/gitlab-org/omnibus-gitlab/blob/8.8.1+ce.0/files/gitlab-ctl-commands/upgrade.rb
posttrans() {
	upgrade

	cat >&2 <<-EOF
		Upgrade complete!

		If you need to roll back to the previous version you can
		use the database backup made during the upgrade (scroll up for the filename).
	EOF
}

# http://docs.gitlab.com/ce/administration/restart_gitlab.html#installations-from-source
restart() {
	local service services=${@-"gitlab-sidekiq gitlab-unicorn gitlab-workhorse"}

	for service in $services; do
		service $service stop
	done
	for service in $services; do
		service $service start
	done
}

# run tail on the logs
# https://github.com/chef/omnibus-ctl/blob/v0.3.6/lib/omnibus-ctl.rb#L427-L436
logtail() {
	# find /var/log -type f -not -path '*/sasl/*' | grep -E -v '(lock|@|tgz|gzip)' | xargs tail --follow=name --retry
	tail -F /var/log/gitlab/*.log
}

usage() {
	cat <<-EOF
Usage: $0: command (subcommand)

backup
  Create a backup of the GitLab system
  http://docs.gitlab.com/ce/raketasks/backup_restore.html

upgrade
  Run migrations after a package upgrade

restart
  Stop the services if they are running, then start them again.

tail
  Watch the service logs of all enabled services.

	EOF
}

COMMAND=$1

if [ -z "$COMMAND" ]; then
	usage
	exit 0
fi

shift
case "$COMMAND" in
preinst)
	preinst
	;;
posttrans)
	posttrans
	;;
backup)
	backup "$@"
	;;
upgrade)
	upgrade "$@"
	;;
restart)
	restart "$@"
	;;
tail)
	logtail "$@"
	;;
esac
