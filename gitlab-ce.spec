# NOTE:
#  This package uses Bundler to download and install all gems in deployment
#  mode (i.e. into isolated directory inside application). That's not PLD Linux
#  way how it should be done, but GitLab has too many dependencies that it will
#  be too difficult to maintain them via distro packages.
#
# install notes: https://gitlab.com/gitlab-org/gitlab-ce/blob/v8.6.6/doc/install/installation.md
#
# TODO
# - [timfel-krb5-auth] doesn't build with heimdal (https://github.com/timfel/krb5-auth/issues/8)
#
#
# Conditional build:
%bcond_with	krb5		# build with kerberos support
%bcond_without	gem_cache	# use local cache to speedup gem installation

Summary:	A Web interface to create projects and repositories, manage access and do code reviews
Name:		gitlab-ce
Version:	8.10.7
Release:	0.52
License:	MIT
Group:		Applications/WWW
# md5 deliberately omitted until this package is useful
Source0:	https://github.com/gitlabhq/gitlabhq/archive/v%{version}/%{name}-%{version}.tar.gz
Source1:	gitlab.target
Source2:	gitlab-sidekiq.service
Source3:	gitlab-sidekiq.init
Source4:	gitlab-unicorn.service
Source5:	gitlab-unicorn.init
Source6:	gitlab.logrotate
Source7:	gitlab.tmpfiles.d
Source8:	gitlab-apache-conf
Source9:	gitlab-rake.sh
Source10:	gitconfig
Source11:	gitlab-ctl.sh
Source12:	clean-vendor.sh
Patch0:		3774.patch
Patch1:		pld.patch
URL:		https://www.gitlab.com/gitlab-ce/
BuildRequires:	cmake
BuildRequires:	gmp-devel
BuildRequires:	libgit2-devel
BuildRequires:	libicu-devel
BuildRequires:	libstdc++-devel
BuildRequires:	libxml2-devel
BuildRequires:	mysql-devel
BuildRequires:	postgresql-devel
BuildRequires:	rpm-rubyprov
BuildRequires:	rpmbuild(macros) >= 1.228
BuildRequires:	ruby-bundler
BuildRequires:	ruby-devel >= 1:2.1.0
BuildRequires:	zlib-devel
Requires(post,preun):	/sbin/chkconfig
Requires:	apache-base
Requires:	git-core >= 2.7.4
Requires:	gitlab-shell >= 3.2.1
Requires:	nodejs
Requires:	rc-scripts
Requires:	ruby-bundler
Suggests:	mysql
Suggests:	redis-server
Obsoletes:	gitlab <= 8.1.4
BuildRoot:	%{tmpdir}/%{name}-%{version}-root-%(id -u -n)

%define	_noautoreqfiles redcloth_scan.jar primitives.jar

%define	uname git
%define gname git
%define homedir %{_localstatedir}/lib/gitlab

%description
GitLab Community Edition (CE) is open source software to collaborate
on code. Create projects and repositories, manage access and do code
reviews. GitLab CE is on-premises software that you can install and
use on your server(s).

%package doc
Summary:	Manual for GitLab
Summary(fr.UTF-8):	Documentation pour GitLab
Summary(it.UTF-8):	Documentazione di GitLab
Summary(pl.UTF-8):	Podręcznik dla GitLab
Group:		Documentation
# noarch subpackages only when building with rpm5
%if "%{_rpmversion}" >= "5"
BuildArch:	noarch
%endif

%description doc
Documentation for GitLab.

%prep
%setup -qn gitlabhq-%{version}
mv config/gitlab.yml.example config/gitlab.yml
mv config/unicorn.rb.example config/unicorn.rb
#%patch0 -p1
%patch1 -p1

# use mysql for now
mv config/database.yml.mysql config/database.yml

find -name .gitkeep | xargs rm
rm -r .github
rm -r docker
rm -r features
rm -r lib/support/{deploy,init.d}
rm -r rubocop
rm -r scripts
rm -r spec
rm .csscomb.json
rm .flayignore
rm .foreman
rm .gitattributes
rm .gitignore
rm .gitlab-ci.yml
rm .pkgr.yml
rm .rspec
rm .rubocop.yml
rm .rubocop_todo.yml
rm .scss-lint.yml
rm .simplecov
rm .vagrant_enabled
rm Procfile
rm bin/pkgr_before_precompile.sh
rm docker-compose.yml

%build
%if %{with gem_cache}
cachedir="%{_specdir}/cache/%{version}.%{_arch}"
install -d vendor/bundle
test -d "$cachedir" && cp -aul "$cachedir"/* vendor/bundle
%endif

bundle install %{_smp_mflags} \
	--verbose \
	--deployment \
	--without development test aws %{!?with_krb5:kerberos}

# install newer rugged to fix diff view showing garbage
# https://gitlab.com/gitlab-org/gitlab-ce/issues/14972
v=0.25.0b6
test -d vendor/bundle/ruby/gems/rugged-$v || \
bundle exec gem install -v $v rugged --no-rdoc --no-ri --verbose

# precompile assets
# use modified config so it doesn't croak
cp -p config/gitlab.yml{,.production}
sed -i -e '/secret_file:/d' config/gitlab.yml
sed -i -e 's#/home/git/repositories/#./#' config/gitlab.yml
bundle exec rake RAILS_ENV=production assets:clean assets:precompile USE_DB=false
mv -f config/gitlab.yml{.production,}

# avoid bogus ruby dep
chmod a-x vendor/bundle/ruby/gems/unicorn-*/bin/unicorn*

# remove secrets, log and cache that assets compile initialized
rm .gitlab_shell_secret
rm .secret
rm config/secrets.yml
rm log/production.log
rm -r tmp/cache/*

%if %{with gem_cache}
install -d "$cachedir"
cp -aul vendor/bundle/* "$cachedir"
%endif

%install
rm -rf $RPM_BUILD_ROOT
install -d \
	$RPM_BUILD_ROOT%{homedir}/www \
	$RPM_BUILD_ROOT%{homedir}/public/{assets,uploads} \
	$RPM_BUILD_ROOT%{homedir}/satellites \
	$RPM_BUILD_ROOT%{homedir}/tmp/{cache/assets,sessions,backups} \
	$RPM_BUILD_ROOT%{_sysconfdir}/gitlab \
	$RPM_BUILD_ROOT%{_docdir}/gitlab \
	$RPM_BUILD_ROOT%{_localstatedir}/{run,log}/gitlab

# test if we can hardlink -- %{_builddir} and $RPM_BUILD_ROOT on same partition
if cp -al VERSION $RPM_BUILD_ROOT/VERSION 2>/dev/null; then
	l=l
	rm -f $RPM_BUILD_ROOT/VERSION
fi

cp -a$l . $RPM_BUILD_ROOT%{homedir}

# cleanup unneccessary cruft (gem build files, etc)
sh -x %{SOURCE12} $RPM_BUILD_ROOT%{homedir}

# replace the contents, yet leave it believe it has proper version installed (for gem dependencies)
v=0.25.0b6
ov=0.24.0
rm -r $RPM_BUILD_ROOT%{homedir}/vendor/bundle/ruby/extensions/%{_arch}-linux/rugged-$ov
mv $RPM_BUILD_ROOT%{homedir}/vendor/bundle/ruby/extensions/%{_arch}-linux/rugged-{$v,$ov}
rm -r $RPM_BUILD_ROOT%{homedir}/vendor/bundle/ruby/gems/rugged-$ov
mv $RPM_BUILD_ROOT%{homedir}/vendor/bundle/ruby/gems/rugged-{$v,$ov}

# rpm cruft from repackaging
rm -f $RPM_BUILD_ROOT%{homedir}/debug*.list

# nuke tests
chmod -R u+w $RPM_BUILD_ROOT%{homedir}/vendor/bundle/ruby/gems/*/test
rm -r $RPM_BUILD_ROOT%{homedir}/vendor/bundle/ruby/gems/*/test

# Creating links
rmdir $RPM_BUILD_ROOT%{homedir}/{log,tmp/{pids,sockets}}
ln -s %{_localstatedir}/run/gitlab $RPM_BUILD_ROOT%{homedir}/tmp/pids
ln -s %{_localstatedir}/run/gitlab $RPM_BUILD_ROOT%{homedir}/tmp/sockets
ln -s %{_localstatedir}/log/gitlab $RPM_BUILD_ROOT%{homedir}/log

move_config() {
	local source=$1 target=$2
	mv $RPM_BUILD_ROOT$source $RPM_BUILD_ROOT$target
	ln -s $target $RPM_BUILD_ROOT$source
}

# Install config files
for f in gitlab.yml unicorn.rb database.yml; do
	move_config %{homedir}/config/$f %{_sysconfdir}/gitlab/$f
done

touch $RPM_BUILD_ROOT%{_sysconfdir}/gitlab/skip-auto-migrations

# relocate to /etc as it's updated runtime, see 77cff54
move_config %{homedir}/db/schema.rb %{_sysconfdir}/gitlab/schema.rb

install -d $RPM_BUILD_ROOT{%{_sbindir},%{systemdunitdir},%{systemdtmpfilesdir}} \
	$RPM_BUILD_ROOT/etc/{logrotate.d,rc.d/init.d,httpd/webapps.d}

cp -p %{SOURCE2} $RPM_BUILD_ROOT%{systemdunitdir}/gitlab-sidekiq.service
install -p %{SOURCE3} $RPM_BUILD_ROOT/etc/rc.d/init.d/gitlab-sidekiq
cp -p %{SOURCE4} $RPM_BUILD_ROOT%{systemdunitdir}/gitlab-unicorn.service
install -p %{SOURCE5} $RPM_BUILD_ROOT/etc/rc.d/init.d/gitlab-unicorn

cp -p %{SOURCE1} $RPM_BUILD_ROOT%{systemdunitdir}/gitlab.target
cp -p %{SOURCE7} $RPM_BUILD_ROOT%{systemdtmpfilesdir}/gitlab.conf
cp -p %{SOURCE6} $RPM_BUILD_ROOT/etc/logrotate.d/gitlab.logrotate
cp -p %{SOURCE8} $RPM_BUILD_ROOT/etc/httpd/webapps.d/gitlab.conf
cp -p %{SOURCE10} $RPM_BUILD_ROOT%{homedir}/.gitconfig
install -p %{SOURCE9} $RPM_BUILD_ROOT%{_sbindir}/gitlab-rake
install -p %{SOURCE11} $RPM_BUILD_ROOT%{_sbindir}/gitlab-ctl

%clean
rm -rf $RPM_BUILD_ROOT

%pre
if [ "$1" = "2" ]; then
	# Looks like an RPM upgrade
	gitlab-ctl preinst
fi

%post
/sbin/chkconfig --add gitlab-sidekiq
/sbin/chkconfig --add gitlab-unicorn
%service gitlab-sidekiq restart
%service gitlab-unicorn restart

if [ $1 -ge 1 ]; then
	systemctl -q daemon-reload
	systemd-tmpfiles --create %{systemdtmpfilesdir}/gitlab.conf
	[ -e %{_localstatedir}/lock/subsys/httpd ] && service httpd reload || :
fi
if [ $1 -eq 1 ]; then
	systemctl -q enable gitlab-unicorn
	systemctl -q enable gitlab-sidekiq
	systemctl -q enable gitlab.target
	systemctl -q start gitlab-unicorn
	systemctl -q start gitlab-sidekiq
	systemctl -q start gitlab.target
	echo "Create and configure database in %{_sysconfdir}/gitlab/database.yml"
	echo "Then run 'sudo -u gitlab bundle exec rake gitlab:setup RAILS_ENV=production'"
	echo
else
	systemctl -q try-restart gitlab-unicorn || :
	systemctl -q try-start gitlab-sidekiq || :
fi

%posttrans
if [ "$1" = "0" ]; then
	# Looks like an RPM upgrade
	gitlab-ctl posttrans
fi

%preun
if [ "$1" = "0" ]; then
	%service -q gitlab-sidekiq stop
	%service -q gitlab-unicorn stop
	/sbin/chkconfig --del gitlab-sidekiq
	/sbin/chkconfig --del gitlab-unicorn
fi

%postun
if [ $1 -eq 0 ]; then
	%userremove gitlab
	%groupremove gitlab
fi

%files
%defattr(644,root,root,755)
%doc LICENSE
%config(noreplace) %verify(not md5 mtime size) %{_sysconfdir}/gitlab/database.yml
%config(noreplace) %verify(not md5 mtime size) %{_sysconfdir}/gitlab/gitlab.yml
%config(noreplace) %verify(not md5 mtime size) %{_sysconfdir}/gitlab/unicorn.rb
%config(noreplace) %verify(not md5 mtime size) %{_sysconfdir}/gitlab/schema.rb
%config(noreplace) %verify(not md5 mtime size) %{_sysconfdir}/httpd/webapps.d/gitlab.conf
%ghost %{_sysconfdir}/gitlab/skip-auto-migrations
/etc/logrotate.d/gitlab.logrotate
%attr(754,root,root) /etc/rc.d/init.d/gitlab-sidekiq
%attr(754,root,root) /etc/rc.d/init.d/gitlab-unicorn
%attr(755,root,root) %{_sbindir}/gitlab-rake
%attr(755,root,root) %{_sbindir}/gitlab-ctl
%{systemdunitdir}/gitlab-sidekiq.service
%{systemdunitdir}/gitlab-unicorn.service
%{systemdunitdir}/gitlab.target
%{systemdtmpfilesdir}/gitlab.conf
%dir %attr(755,%{uname},%{gname}) %{homedir}
%dir %attr(640,%{uname},%{gname}) %{homedir}/.gitconfig
%dir %attr(755,%{uname},%{gname}) %{homedir}/app
%attr(-,%{uname},%{gname}) %{homedir}/app/*
%dir %{homedir}/bin
%attr(-,root,root) %{homedir}/bin/*
%dir %attr(755,%{uname},%{gname}) %{homedir}/builds
%dir %attr(755,%{uname},%{gname}) %{homedir}/config
%attr(-,%{uname},%{gname}) %{homedir}/config/*
%{homedir}/db
%{homedir}/fixtures
%{homedir}/generator_templates
%{homedir}/lib

%dir %{homedir}/public
%{homedir}/public/ci
%{homedir}/public/*.*
%attr(-,%{uname},%{gname}) %{homedir}/public/uploads
%attr(-,%{uname},%{gname}) %{homedir}/public/assets
%dir %attr(755,%{uname},%{gname}) %{homedir}/satellites

%dir %attr(755,%{uname},%{gname}) %{homedir}/tmp
%attr(-,%{uname},%{gname}) %{homedir}/tmp/backups
%attr(-,%{uname},%{gname}) %{homedir}/tmp/cache
%attr(-,%{uname},%{gname}) %{homedir}/tmp/sessions
%attr(-,%{uname},%{gname}) %{homedir}/tmp/sockets
%attr(-,%{uname},%{gname}) %{homedir}/tmp/pids

%dir %attr(755,%{uname},%{gname}) %{homedir}/www

%dir %attr(750,%{uname},%{gname}) %{homedir}/shared
%dir %attr(750,%{uname},%{gname}) %{homedir}/shared/artifacts
%dir %attr(750,%{uname},%{gname}) %{homedir}/shared/artifacts/tmp
%dir %attr(750,%{uname},%{gname}) %{homedir}/shared/artifacts/tmp/cache
%dir %attr(750,%{uname},%{gname}) %{homedir}/shared/artifacts/tmp/uploads
%dir %attr(750,%{uname},%{gname}) %{homedir}/shared/lfs-objects
%dir %attr(750,%{uname},%{gname}) %{homedir}/shared/registry

%dir %attr(755,%{uname},%{gname}) %{homedir}/.bundle
%attr(-,%{uname},%{gname}) %{homedir}/.bundle/config
%attr(-,%{uname},%{gname}) %{homedir}/.ruby-version
%attr(-,%{uname},%{gname}) %{homedir}/CHANGELOG
%attr(-,%{uname},%{gname}) %{homedir}/GITLAB_WORKHORSE_VERSION
%attr(-,%{uname},%{gname}) %{homedir}/GITLAB_SHELL_VERSION
%attr(-,%{uname},%{gname}) %{homedir}/Gemfile*
%attr(-,%{uname},%{gname}) %{homedir}/LICENSE
%attr(-,%{uname},%{gname}) %{homedir}/*.md
%attr(-,%{uname},%{gname}) %{homedir}/Rakefile
%attr(-,%{uname},%{gname}) %{homedir}/VERSION
%attr(-,%{uname},%{gname}) %{homedir}/config.ru

%{homedir}/log
%dir %attr(771,root,%{gname}) %{_localstatedir}/log/gitlab
%dir %attr(771,root,%{gname}) %{_localstatedir}/run/gitlab

%defattr(-,root,root,-)
%dir %{homedir}/vendor
%{homedir}/vendor/*

%files doc
%defattr(644,root,root,755)
%{homedir}/doc
