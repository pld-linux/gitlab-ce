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
%bcond_without	gem_cache	# use local to speedup gem installation

Summary:	A Web interface to create projects and repositories, manage access and do code reviews
Name:		gitlab-ce
Version:	8.6.6
Release:	0.2
License:	MIT
Group:		Applications/WWW
# md5 deliberately omitted until this package is useful
Source0:	https://github.com/gitlabhq/gitlabhq/archive/v%{version}/%{name}-%{version}.tar.gz
URL:		https://www.gitlab.com/gitlab-ce/
Source1:	gitlab.target
Source2:	gitlab-sidekiq.service
Source3:	gitlab-unicorn.service
Source4:	gitlab.logrotate
Source5:	gitlab.tmpfiles.d
Source6:	gitlab-apache-conf
BuildRequires:	cmake
BuildRequires:	gmp-devel
BuildRequires:	libicu-devel
BuildRequires:	libstdc++-devel
BuildRequires:	libxml2-devel
BuildRequires:	libxslt-devel
BuildRequires:	mysql-devel
BuildRequires:	postgresql-devel
BuildRequires:	ruby-bundler
BuildRequires:	ruby-devel >= 1:2.1.0
BuildRequires:	zlib-devel
Obsoletes:	gitlab <= 8.1.4
Requires(pre):	gitlab-shell
Requires:	apache-base
Requires:	git-core >= 2.7.4
Requires:	ruby-bundler
Suggests:	mysql
Suggests:	redis-server
BuildRoot:	%{tmpdir}/%{name}-%{version}-root-%(id -u -n)

%define	_noautoreqfiles redcloth_scan.jar primitives.jar

%define gitlab_uid 65434
%define gitlab_gid 65434

%define     homedir       %{_localstatedir}/lib/gitlab

%description
GitLab Community Edition (CE) is open source software to collaborate
on code. Create projects and repositories, manage access and do code
reviews. GitLab CE is on-premises software that you can install and
use on your server(s).

%prep
%setup -qn gitlabhq-%{version}

# Patching config files:
sed -e "s|# user: git|user: gitlab|" \
	-e "s|/home/git/repositories|%{homedir}/repositories|" \
	-e "s|/home/git/gitlab-satellites|%{homedir}/satellites|" \
	-e "s|/home/git/gitlab-shell|/usr/share/gitlab-shell|" \
	config/gitlab.yml.example > config/gitlab.yml
sed -e "s|/home/git/gitlab/tmp/.*/|/run/gitlab/|g" \
	-e "s|/home/git/gitlab|%{homedir}|g" \
	-e "s|/usr/share/gitlab/log|%{homedir}/log|g" \
	-e "s|timeout 30|timeout 300|" \
	config/unicorn.rb.example > config/unicorn.rb
sed -e "s|username: git|username: gitlab|" \
	config/database.yml.mysql > config/database.yml

rm .flayignore
rm .gitignore
rm .csscomb.json
find -name .gitkeep | xargs rm

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

# avoid bogus ruby dep
chmod a-x vendor/bundle/ruby/gems/unicorn-*/bin/unicorn*

%if %{with gem_cache}
install -d "$cachedir"
cp -aul vendor/bundle/* "$cachedir"
%endif

%install
rm -rf $RPM_BUILD_ROOT
install -d \
    $RPM_BUILD_ROOT%{homedir}/www \
    $RPM_BUILD_ROOT%{homedir}/public/uploads \
	$RPM_BUILD_ROOT%{_sysconfdir}/gitlab \
    $RPM_BUILD_ROOT%{_docdir}/gitlab \
    $RPM_BUILD_ROOT%{homedir}/satellites

# test if we can hardlink -- %{_builddir} and $RPM_BUILD_ROOT on same partition
if cp -al VERSION $RPM_BUILD_ROOT/VERSION 2>/dev/null; then
	l=l
	rm -f $RPM_BUILD_ROOT/VERSION
fi

cp -a$l . $RPM_BUILD_ROOT%{homedir}

# Creating links
ln -fs /run/gitlab $RPM_BUILD_ROOT%{homedir}/pids
ln -fs /run/gitlab $RPM_BUILD_ROOT%{homedir}/sockets
ln -fs %{_localstatedir}/log/gitlab $RPM_BUILD_ROOT%{homedir}/log
install -d $RPM_BUILD_ROOT%{_localstatedir}/log/gitlab

# Install config files
for f in gitlab.yml unicorn.rb database.yml; do
	install -m0644 config/$f $RPM_BUILD_ROOT%{_sysconfdir}/gitlab/$f
	[ -f "$RPM_BUILD_ROOT%{homedir}/config/$f" ] && rm $RPM_BUILD_ROOT%{homedir}/config/$f
	ln -fs %{_sysconfdir}/gitlab/$f $RPM_BUILD_ROOT%{homedir}/config/
done

# Install systemd service files
install -D %{S:1} $RPM_BUILD_ROOT%{systemdunitdir}/gitlab.target
install -D %{S:2} $RPM_BUILD_ROOT%{systemdunitdir}/gitlab-sidekiq.service
install -D %{S:3} $RPM_BUILD_ROOT%{systemdunitdir}/gitlab-unicorn.service
install -D %{S:4} $RPM_BUILD_ROOT%{_sysconfdir}/logrotate.d/gitlab.logrotate
install -D %{S:5} $RPM_BUILD_ROOT%{systemdtmpfilesdir}/gitlab.conf
install -D %{S:6} $RPM_BUILD_ROOT%{_sysconfdir}/httpd/httpd.d/gitlab.conf

%clean
rm -rf "$RPM_BUILD_ROOT"

%pre
if [ $1 -ge 1 ]; then
	%groupadd gitlab -g %{gitlab_gid}
	%useradd -u %{gitlab_uid} -c 'Gitlab user' -d %{homedir} -g gitlab -s /bin/bash gitlab
fi

%post
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
	sudo -u gitlab -H git config --global user.name "GitLab"
	sudo -u gitlab -H git config --global user.email "gitlab@localhost"
	sudo -u gitlab -H git config --global core.autocrlf input
	echo "Create and configure database in /etc/gitlab/database.yml"
	echo "Then run 'sudo -u gitlab bundle exec rake gitlab:setup RAILS_ENV=production'"
	echo
else
	systemctl -q try-restart gitlab-unicorn
	systemctl -q try-start gitlab-sidekiq
fi

%postun
if [ $1 -eq 0 ]; then
	%userremove gitlab
	%groupremove gitlab
fi

%files
%defattr(644,root,root,755)
%doc LICENSE
%dir %{_sysconfdir}/gitlab
%config(noreplace) %{_sysconfdir}/gitlab/database.yml
%config(noreplace) %{_sysconfdir}/gitlab/gitlab.yml
%config(noreplace) %{_sysconfdir}/gitlab/unicorn.rb
%dir /etc/httpd
%dir /etc/httpd/httpd.d
%config(noreplace) %{_sysconfdir}/httpd/httpd.d/gitlab.conf
/etc/logrotate.d/gitlab.logrotate
%{systemdunitdir}/gitlab-sidekiq.service
%{systemdunitdir}/gitlab-unicorn.service
%{systemdunitdir}/gitlab.target
%{systemdtmpfilesdir}/gitlab.conf
%dir %attr(755,gitlab,gitlab) %{homedir}
%dir %attr(755,gitlab,gitlab) %{homedir}/app
%attr(-,gitlab,gitlab) %{homedir}/app/*
%dir %attr(755,gitlab,gitlab) %{homedir}/bin
%attr(-,gitlab,gitlab) %{homedir}/bin/*
%dir %attr(755,gitlab,gitlab) %{homedir}/builds
%dir %attr(755,gitlab,gitlab) %{homedir}/config
%attr(-,gitlab,gitlab) %{homedir}/config/*
%dir %attr(755,gitlab,gitlab) %{homedir}/db
%attr(-,gitlab,gitlab) %{homedir}/db/*
%dir %attr(755,gitlab,gitlab) %{homedir}/doc
%attr(-,gitlab,gitlab) %{homedir}/doc/*
%dir %attr(755,gitlab,gitlab) %{homedir}/docker
%attr(-,gitlab,gitlab) %{homedir}/docker/*
%dir %attr(755,gitlab,gitlab) %{homedir}/features
%attr(-,gitlab,gitlab) %{homedir}/features/*
%dir %attr(755,gitlab,gitlab) %{homedir}/lib
%attr(-,gitlab,gitlab) %{homedir}/lib/*
%dir %attr(755,gitlab,gitlab) %{homedir}/log
%attr(-,gitlab,gitlab) %{homedir}/log/*
%dir %attr(755,gitlab,gitlab) %{homedir}/pids
%dir %attr(755,gitlab,gitlab) %{homedir}/public
%attr(-,gitlab,gitlab) %{homedir}/public/*
%dir %attr(755,gitlab,gitlab) %{homedir}/satellites
%dir %attr(755,gitlab,gitlab) %{homedir}/scripts
%attr(-,gitlab,gitlab) %{homedir}/scripts/*
%dir %attr(755,gitlab,gitlab) %{homedir}/sockets
%dir %attr(755,gitlab,gitlab) %{homedir}/spec
%attr(-,gitlab,gitlab) %{homedir}/spec/*
%dir %attr(755,gitlab,gitlab) %{homedir}/tmp
%attr(-,gitlab,gitlab) %{homedir}/tmp/*
%dir %{homedir}/vendor
%{homedir}/vendor/*
%dir %attr(755,gitlab,gitlab) %{homedir}/www

%dir %attr(755,gitlab,gitlab) %{homedir}/.bundle
%attr(-,gitlab,gitlab) %{homedir}/.bundle/config
%attr(-,gitlab,gitlab) %{homedir}/.foreman
%attr(-,gitlab,gitlab) %{homedir}/docker-compose.yml
%attr(-,gitlab,gitlab) %{homedir}/.gitattributes
%attr(-,gitlab,gitlab) %{homedir}/.*.yml
%attr(-,gitlab,gitlab) %{homedir}/.rspec
%attr(-,gitlab,gitlab) %{homedir}/.ruby-version
%attr(-,gitlab,gitlab) %{homedir}/.simplecov
%attr(-,gitlab,gitlab) %{homedir}/CHANGELOG
%attr(-,gitlab,gitlab) %{homedir}/GITLAB_WORKHORSE_VERSION
%attr(-,gitlab,gitlab) %{homedir}/GITLAB_SHELL_VERSION
%attr(-,gitlab,gitlab) %{homedir}/Gemfile*
%attr(-,gitlab,gitlab) %{homedir}/LICENSE
%attr(-,gitlab,gitlab) %{homedir}/*.md
%attr(-,gitlab,gitlab) %{homedir}/Procfile
%attr(-,gitlab,gitlab) %{homedir}/Rakefile
%attr(-,gitlab,gitlab) %{homedir}/VERSION
%attr(-,gitlab,gitlab) %{homedir}/config.ru
%attr(-,gitlab,gitlab) %{homedir}/fixtures
