#!/bin/sh
PROG=${0##*/}
if [ $# = 2 ]; then
	# for using same syntax as rpm own find-lang
	RPM_BUILD_ROOT=$1
	shift
fi
dir=$RPM_BUILD_ROOT/usr/lib/gitlab/locale
langfile=$1
tmp=$(mktemp) || exit 1
rc=0

find $dir -name '*.po' > $tmp

echo '%defattr(644,root,root,755)' > $langfile
while read file; do
	lang=${file##*/}
	lang=${lang%.po}
	case "$lang" in
	*-*)
		echo >&2 "ERROR: Need mapping for $lang!"
		rc=1
	;;
	esac
	echo "%lang($lang) ${file#$RPM_BUILD_ROOT}" >> $langfile
done < $tmp

if [ "$(grep -Ev '(^%defattr|^$)' $langfile | wc -l)" -le 0 ]; then
	echo >&2 "$PROG: Error: international files not found!"
	rc=1
fi

rm -f $tmp
exit $rc
