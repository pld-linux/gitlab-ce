#!/bin/sh
# Frontend to Gitlab Rake tasks
#
# http://docs.gitlab.com/ce/raketasks/
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

# Rake with no params does nothing useful
# (currently it switches env production->test and then fails)
# so instead show defined tasks
test $# = 0 && set -- -T

cd /var/lib/gitlab
exec sudo -u git bundle exec rake RAILS_ENV=production "$@"
