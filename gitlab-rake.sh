#!/bin/sh
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

cd /var/lib/gitlab
exec sudo -u git bundle exec rake RAILS_ENV=production "$@"
