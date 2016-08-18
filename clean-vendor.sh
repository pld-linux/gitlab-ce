#!/bin/sh
set -e

clean_rubygems() {
	cd $vendordir/vendor/bundle/ruby

	# cleanup gem work files
	# the files are not needed at runtime
	# and the gem command is not ran there anymore
	rm -rfv build_info
	rm -rfv cache
	rm -rfv doc

	# we need just .so in extensions dir
	# however the .so may be in subdirs
	rm -fv extensions/*/*-*/gem.*
	rm -fv extensions/*/*-*/gem_*
	rm -fv extensions/*/*-*/mkmf.log

	# contains package dirs
	# ideally we just need 'lib' dirs from each gem

	# spec/ contains files for rspec testing
	rm -rfv gems/*/spec

	# and some other files
	rm -fv gems/*/*.gemspec
	rm -fv gems/*/*.md
	rm -fv gems/*/*.sh
	rm -fv gems/*/Gemfile
	rm -fv gems/*/Guardfile
	rm -fv gems/*/Rakefile
	rm -rfv gems/*/Documentation
	rm -rfv gems/*/bench
	rm -rfv gems/*/contrib
	rm -rfv gems/*/doc
	rm -rfv gems/*/doc-api
	rm -rfv gems/*/examples
	rm -rfv gems/*/ext
	rm -rfv gems/*/gemfiles
	rm -rfv gems/*/libtest
	rm -rfv gems/*/man
	rm -rfv gems/*/script
	rm -rfv gems/*/t
	rm -rfv gems/*/tests
	rm -rfv gems/*/sample_documents
	rm -rfv gems/*/fixtures
	rm -rfv gems/*/samples
	rm -fv gems/*/run_tests.rb
	rm -fv gems/*/*LICENSE*
	rm -fv gems/*/CHANGES*
	rm -fv gems/*/README*

	# clean selected vendor, because:
	# LoadError: cannot load such file -- dependency_detection
	#rm -rfv gems/*/vendor
	rm -rfv rugged-*/vendor/libgit2
}

vendordir=$1

clean_rubygems
