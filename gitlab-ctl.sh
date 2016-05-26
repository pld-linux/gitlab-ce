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

# Run backup before package upgrade
# https://gitlab.com/gitlab-org/omnibus-gitlab/blob/8.8.1+ce.0/config/templates/package-scripts/preinst.erb#L10
backup_before_upgrade() {
	if ! gitlab-rake gitlab:backup:create SKIP=repositories,uploads,builds,artifacts,lfs,registry; then
		cat >&2 <<-EOF

		Backup failed! If you want to skip this backup, run the following command and try again:

		touch ${auto_migrations_skip_file}

		EOF
		exit 1
	fi
}

# Run migrations after a package upgrade
# https://gitlab.com/gitlab-org/omnibus-gitlab/blob/8.8.1+ce.0/files/gitlab-ctl-commands/upgrade.rb
upgrade() {
	gitlab-rake db:migrate
}

# Run migrations after a package upgrade
pkg_upgrade() {
	if [ -f $auto_migrations_skip_file ]; then
		echo >&2 "Found $auto_migrations_skip_file, exiting..."
		return
	fi

	backup_before_upgrade
	upgrade

	cat >&2 <<-EOF
		Upgrade complete!

		If you need to roll back to the previous version you can
		use the database backup made during the upgrade (scroll up for the filename).
	EOF

}

# http://docs.gitlab.com/ce/administration/restart_gitlab.html#installations-from-source
restart() {
	:
}

case "$1" in
pkg-upgrade)
	pkg_upgrade
	;;
upgrade)
	upgrade
	;;
esac
