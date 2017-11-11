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

%define	shell_version 5.9.3
%define	workhorse_version 3.2.0
%define	pages_version 0.6.0
%define	gitaly_version 0.43.1
Summary:	A Web interface to create projects and repositories, manage access and do code reviews
Name:		gitlab-ce
Version:	10.1.2
Release:	1
License:	MIT
Group:		Applications/WWW
# md5 deliberately omitted until this package is useful
Source0:	https://gitlab.com/gitlab-org/gitlab-ce/repository/archive.tar.bz2?ref=v%{version}&/%{name}-%{version}.tar.bz2
Source1:	gitlab.target
Source2:	gitlab-sidekiq.service
Source3:	gitlab-sidekiq.init
Source4:	gitlab-unicorn.service
Source5:	gitlab-unicorn.init
Source6:	gitlab.logrotate
Source7:	gitlab.tmpfiles.d
Source8:	apache.conf
Source9:	gitlab-rake.sh
Source10:	gitlab-rails.sh
Source11:	gitlab-ctl.sh
Source12:	clean-vendor.sh
Source13:	nginx.conf
Source14:	gitconfig
Source15:	find-lang.sh
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
BuildRequires:	rpmbuild(macros) >= 1.647
BuildRequires:	ruby-bundler
BuildRequires:	ruby-devel >= 1:2.3.5-4
BuildRequires:	ruby-rubygems >= 2.6.9
BuildRequires:	yarn >= 1.1.0
BuildRequires:	zlib-devel
Requires(post,preun):	/sbin/chkconfig
Requires:	git-core >= 2.7.4
Requires:	gitlab-common >= 8.12-2
Requires:	gitlab-shell >= %{shell_version}
Requires:	gitlab-workhorse >= %{workhorse_version}
Requires:	nodejs
Requires:	rc-scripts
Requires:	ruby-bundler
Requires:	systemd-units >= 0.38
Requires:	webapps
Suggests:	mysql
Suggests:	redis-server
Obsoletes:	gitlab <= 8.1.4
BuildRoot:	%{tmpdir}/%{name}-%{version}-root-%(id -u -n)

%define	find_lang	sh %{SOURCE15} %{buildroot}

%define	_noautoreqfiles redcloth_scan.jar primitives.jar

%define uname    git
%define gname    git
%define appdir   %{_prefix}/lib/gitlab
%define vardir   %{_localstatedir}/lib/gitlab
%define cachedir %{_localstatedir}/cache/gitlab
%define _webapps /etc/webapps
%define _webapp  gitlab

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
%setup -qc
mv gitlab-ce-v%{version}-*/{.??*,*} .
mv config/gitlab.yml.example config/gitlab.yml
mv config/unicorn.rb.example config/unicorn.rb
%patch1 -p1

# use mysql for now
mv config/database.yml.mysql config/database.yml

find -name .gitkeep | xargs rm

%build
v=$(cat GITLAB_SHELL_VERSION)
test "$v" = "%{shell_version}"
v=$(cat GITLAB_WORKHORSE_VERSION)
test "$v" = "%{workhorse_version}"
v=$(cat GITLAB_PAGES_VERSION)
test "$v" = "%{pages_version}"
v=$(cat GITALY_SERVER_VERSION)
test "$v" = "%{gitaly_version}"

%if %{with gem_cache}
cachedir="%{_specdir}/cache/%{version}.%{_arch}"
install -d vendor/bundle
test -d "$cachedir" && cp -aul "$cachedir"/* vendor/bundle
%endif

# enable-gems to workaround https://github.com/ruby-prof/ruby-prof/pull/191
# until https://gitlab.com/gitlab-org/gitlab-ce/merge_requests/6026 is merged
RUBYOPT=--enable-gems \
bundle install %{_smp_mflags} \
	--verbose \
	--deployment \
	--without development test aws %{!?with_krb5:kerberos}

# install webpack deps, used later by rake webpack:compile:
# node_modules/.bin/webpack --config config/webpack.config.js --bail
# see vendor/bundle/ruby/gems/webpack-rails-0.9.9/lib/tasks/webpack.rake
test -d node_modules || \
yarn install --pure-lockfile

# precompile assets
# https://gitlab.com/gitlab-org/omnibus-gitlab/blob/8.17.5+ce.0/config/software/gitlab-rails.rb
# use modified config so it doesn't croak
cp -p config/gitlab.yml{,.production}
sed -i -e '/secret_file:/d' config/gitlab.yml
sed -i -e 's#/var/lib/gitlab/repositories/#./#' config/gitlab.yml
bundle exec rake RAILS_ENV=production gitlab:assets:clean gitlab:assets:compile USE_DB=false
mv -f config/gitlab.yml{.production,}

# avoid bogus ruby dep
chmod a-x vendor/bundle/ruby/%{ruby_version}/gems/unicorn-*/bin/unicorn*

# remove secrets, log and cache that assets compile initialized
rm .gitlab_shell_secret
cp -f config/secrets.yml{.example,}
rm log/production.log
rm -r tmp/cache/*

%if %{with gem_cache}
install -d "$cachedir"
cp -aul vendor/bundle/* "$cachedir"
%endif

%install
rm -rf $RPM_BUILD_ROOT
install -d \
	$RPM_BUILD_ROOT%{appdir}/public/{assets,uploads} \
	$RPM_BUILD_ROOT%{appdir}/tmp/{cache/assets,sessions,backups} \
	$RPM_BUILD_ROOT%{appdir}/shared/tmp/project_exports \
	$RPM_BUILD_ROOT%{_sysconfdir}/gitlab \
	$RPM_BUILD_ROOT%{_webapps}/%{_webapp} \
	$RPM_BUILD_ROOT%{_docdir}/gitlab \
	$RPM_BUILD_ROOT%{vardir}/public \
	$RPM_BUILD_ROOT%{cachedir}/tmp \
	$RPM_BUILD_ROOT%{_localstatedir}/run/gitlab

# test if we can hardlink -- %{_builddir} and $RPM_BUILD_ROOT on same partition
if cp -al VERSION $RPM_BUILD_ROOT/VERSION 2>/dev/null; then
	l=l
	rm -f $RPM_BUILD_ROOT/VERSION
fi

cp -a$l . $RPM_BUILD_ROOT%{appdir}

# cleanup unneccessary cruft (gem build files, etc)
sh -x %{SOURCE12} $RPM_BUILD_ROOT%{appdir}

%find_lang %{name}.lang

# rpm cruft from repackaging
rm -f $RPM_BUILD_ROOT%{appdir}/debug*.list
rm -f $RPM_BUILD_ROOT%{appdir}/%{name}.lang

# Creating links
mv $RPM_BUILD_ROOT%{appdir}/tmp/sockets/* $RPM_BUILD_ROOT%{_localstatedir}/run/gitlab
rmdir $RPM_BUILD_ROOT%{appdir}/{log,tmp/{pids,sockets}}
ln -s %{_localstatedir}/run/gitlab $RPM_BUILD_ROOT%{appdir}/tmp/pids
ln -s %{_localstatedir}/run/gitlab $RPM_BUILD_ROOT%{appdir}/tmp/sockets
ln -s %{_localstatedir}/log/gitlab $RPM_BUILD_ROOT%{appdir}/log

# move $source to $target leaving symlink in original path
move_symlink() {
	local source=$1 target=$2
	mv $RPM_BUILD_ROOT$source $RPM_BUILD_ROOT$target
	ln -s $target $RPM_BUILD_ROOT$source
}

# Install config files
for f in gitlab.yml unicorn.rb database.yml secrets.yml; do
	move_symlink %{appdir}/config/$f %{_sysconfdir}/gitlab/$f
done
move_symlink %{appdir}/.gitlab_workhorse_secret %{_sysconfdir}/gitlab/.gitlab_workhorse_secret

cp -p %{SOURCE14} $RPM_BUILD_ROOT%{_sysconfdir}/gitlab/.gitconfig
ln -s %{_sysconfdir}/gitlab/.gitconfig $RPM_BUILD_ROOT%{vardir}/.gitconfig

touch $RPM_BUILD_ROOT%{_sysconfdir}/gitlab/skip-auto-migrations

# relocate to /etc as it's updated runtime, see 77cff54
move_symlink %{appdir}/db/schema.rb %{_sysconfdir}/gitlab/schema.rb

for a in builds shared tmp public/{uploads,assets}; do
	move_symlink %{appdir}/$a %{vardir}/$a
done

move_symlink %{vardir}/tmp/cache %{cachedir}/cache
move_symlink %{vardir}/shared/artifacts/tmp/cache %{cachedir}/artifacts

install -d $RPM_BUILD_ROOT{%{_sbindir},%{systemdunitdir},%{systemdtmpfilesdir}} \
	$RPM_BUILD_ROOT/etc/{logrotate.d,rc.d/init.d,httpd/webapps.d}

cp -p %{SOURCE2} $RPM_BUILD_ROOT%{systemdunitdir}/gitlab-sidekiq.service
install -p %{SOURCE3} $RPM_BUILD_ROOT/etc/rc.d/init.d/gitlab-sidekiq
cp -p %{SOURCE4} $RPM_BUILD_ROOT%{systemdunitdir}/gitlab-unicorn.service
install -p %{SOURCE5} $RPM_BUILD_ROOT/etc/rc.d/init.d/gitlab-unicorn

cp -p %{SOURCE1} $RPM_BUILD_ROOT%{systemdunitdir}/gitlab.target
cp -p %{SOURCE7} $RPM_BUILD_ROOT%{systemdtmpfilesdir}/gitlab.conf
cp -p %{SOURCE6} $RPM_BUILD_ROOT/etc/logrotate.d/gitlab
cp -p %{SOURCE8} $RPM_BUILD_ROOT%{_webapps}/%{_webapp}/httpd.conf
install -p %{SOURCE9} $RPM_BUILD_ROOT%{_sbindir}/gitlab-rake
install -p %{SOURCE10} $RPM_BUILD_ROOT%{_sbindir}/gitlab-rails
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
%systemd_post gitlab-sidekiq.service gitlab-unicorn.service

%banner -e -o %{name} << EOF

Create and configure database in %{_sysconfdir}/gitlab/database.yml

Then run:
  # gitlab-rake gitlab:setup

EOF

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
%systemd_preun gitlab-sidekiq.service gitlab-unicorn.service

%postun
if [ $1 -eq 0 ]; then
	%userremove gitlab
	%groupremove gitlab
fi
%systemd_reload

%triggerin -- apache < 2.2.0, apache-base
%webapp_register httpd %{_webapp}

%triggerun -- apache < 2.2.0, apache-base
%webapp_unregister httpd %{_webapp}

%files -f %{name}.lang
%defattr(644,root,root,755)
%doc LICENSE
%config(noreplace) %verify(not md5 mtime size) %{_sysconfdir}/gitlab/database.yml
%config(noreplace) %verify(not md5 mtime size) %{_sysconfdir}/gitlab/gitlab.yml
%config(noreplace) %verify(not md5 mtime size) %{_sysconfdir}/gitlab/unicorn.rb
%config(noreplace) %verify(not md5 mtime size) %attr(640,%{uname},%{gname}) %{_sysconfdir}/gitlab/schema.rb
%config(noreplace) %verify(not md5 mtime size) %attr(640,%{uname},%{gname}) %{_sysconfdir}/gitlab/secrets.yml
%config(noreplace) %verify(not md5 mtime size) %attr(640,%{uname},%{gname}) %{_sysconfdir}/gitlab/.gitconfig
%config(noreplace) %verify(not md5 mtime size) %attr(640,%{uname},%{gname}) %{_sysconfdir}/gitlab/.gitlab_workhorse_secret

%dir %attr(750,root,http) %{_webapps}/%{_webapp}
%attr(640,root,root) %config(noreplace) %verify(not md5 mtime size) %{_webapps}/%{_webapp}/httpd.conf

%ghost %{_sysconfdir}/gitlab/skip-auto-migrations
%config(noreplace) %verify(not md5 mtime size) /etc/logrotate.d/gitlab
%attr(754,root,root) /etc/rc.d/init.d/gitlab-sidekiq
%attr(754,root,root) /etc/rc.d/init.d/gitlab-unicorn
%attr(755,root,root) %{_sbindir}/gitlab-ctl
%attr(755,root,root) %{_sbindir}/gitlab-rails
%attr(755,root,root) %{_sbindir}/gitlab-rake
%{systemdunitdir}/gitlab-sidekiq.service
%{systemdunitdir}/gitlab-unicorn.service
%{systemdunitdir}/gitlab.target
%{systemdtmpfilesdir}/gitlab.conf

%dir %{appdir}
%dir %{appdir}/bin
%attr(-,root,root) %{appdir}/bin/*
# files
%{appdir}/*.md
%{appdir}/.bundle
%{appdir}/.gitlab_workhorse_secret
%{appdir}/.ruby-version
%{appdir}/GITALY_SERVER_VERSION
%{appdir}/GITLAB_PAGES_VERSION
%{appdir}/GITLAB_SHELL_VERSION
%{appdir}/GITLAB_WORKHORSE_VERSION
%{appdir}/Gemfile*
%{appdir}/LICENSE
%{appdir}/Rakefile
%{appdir}/VERSION
%{appdir}/config.ru

# dirs
%{appdir}/app
%{appdir}/builds
%{appdir}/config
%{appdir}/db
%{appdir}/fixtures
%{appdir}/generator_templates
%{appdir}/lib
%{appdir}/log
%{appdir}/public
%{appdir}/shared
%{appdir}/symbol
%{appdir}/tmp

%{vardir}/.gitconfig
%dir %attr(755,%{uname},%{gname}) %{vardir}/builds
%dir %{vardir}/public
%attr(-,%{uname},%{gname}) %{vardir}/public/uploads
%attr(-,%{uname},%{gname}) %{vardir}/public/assets
%dir %attr(755,%{uname},%{gname}) %{vardir}/tmp
%attr(-,%{uname},%{gname}) %{vardir}/tmp/backups
%{vardir}/tmp/cache
%attr(-,%{uname},%{gname}) %{vardir}/tmp/sessions
%attr(-,%{uname},%{gname}) %{vardir}/tmp/sockets
%attr(-,%{uname},%{gname}) %{vardir}/tmp/pids
%dir %attr(750,%{uname},%{gname}) %{vardir}/shared
%dir %attr(750,%{uname},%{gname}) %{vardir}/shared/artifacts
%dir %attr(750,%{uname},%{gname}) %{vardir}/shared/artifacts/tmp
%{vardir}/shared/artifacts/tmp/cache
%dir %attr(750,%{uname},%{gname}) %{vardir}/shared/artifacts/tmp/uploads
%dir %attr(750,%{uname},%{gname}) %{vardir}/shared/lfs-objects
%dir %attr(750,%{uname},%{gname}) %{vardir}/shared/registry
%dir %attr(750,%{uname},%{gname}) %{vardir}/shared/pages
%dir %attr(750,%{uname},%{gname}) %{vardir}/shared/tmp
%dir %attr(750,%{uname},%{gname}) %{vardir}/shared/tmp/project_exports

%dir %attr(750,root,%{gname}) %{cachedir}
%attr(-,%{uname},%{gname}) %{cachedir}/cache
%dir %attr(750,%{uname},%{gname}) %{cachedir}/artifacts

%dir %attr(771,root,%{gname}) %{_localstatedir}/run/gitlab

%dir %{appdir}/locale

%defattr(-,root,root,-)
%dir %{appdir}/vendor
%{appdir}/vendor/*

%files doc
%defattr(644,root,root,755)
%{appdir}/doc
