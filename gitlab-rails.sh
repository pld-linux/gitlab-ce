#!/bin/sh
# GitLab Rails console session
#
# https://docs.gitlab.com/omnibus/maintenance/README.html#starting-a-rails-console-session
#
set -e

# Unset ENV variables that might interfere with
# omnibus-gitlab ruby env (looking at you rvm)
for ruby_env_var in RUBYOPT \
                    BUNDLE_BIN_PATH \
                    BUNDLE_GEMFILE \
                    GEM_PATH \
                    GEM_HOME
do
	unset $ruby_env_var
done


cd /usr/lib/gitlab
exec sudo -H -u git bundle exec rails "$@"
