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

# http://docs.gitlab.com/ce/administration/restart_gitlab.html#installations-from-source
restart() {
	:
}

# Run backup before package upgrade
# https://gitlab.com/gitlab-org/omnibus-gitlab/blob/8.8.1+ce.0/config/templates/package-scripts/preinst.erb#L10
preinst() {
	if [ -f $auto_migrations_skip_file ]; then
		notice "preinstall: Found $auto_migrations_skip_file, skipping auto backup..."
		return
	fi

	notice "preinstall: Automatically backing up only the GitLab SQL database (excluding everything else!)"

	if ! backup SKIP=repositories,uploads,builds,artifacts,lfs,registry; then
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

case "$1" in
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
esac
