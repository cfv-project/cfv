#! /usr/bin/env python

#    benchmark.py - cfv benchmarker
#    Copyright (C) 2013  Matthew Mueller <donut AT users DOT sourceforge DOT net>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA


import argparse
import os
import math
import random

import cfvtest


def human_int(value):
	'''Convert values with size suffix to integers.
	>>> human_int('10')
	10
	>>> human_int('10K')
	10240
	>>> human_int('10M')
	10485760
	>>> human_int('10G')
	10737418240
	>>> human_int('') #doctest: +IGNORE_EXCEPTION_DETAIL
	Traceback (most recent call last):
	ValueError:
	>>> human_int('G') #doctest: +IGNORE_EXCEPTION_DETAIL
	Traceback (most recent call last):
	ValueError:
	>>> human_int('10X') #doctest: +IGNORE_EXCEPTION_DETAIL
	Traceback (most recent call last):
	ValueError:
	'''
	if len(value) < 1:
		return int(value)
	suffixes = {'K': 2**10, 'M': 2**20, 'G': 2**30}
	multiplier = 1
	if value[-1] in suffixes:
		multiplier = suffixes[value[-1]]
		value = value[:-1]
	return int(value) * multiplier


def create_test_file(path, max_size, verbose=False):
	size = random.randint(1, max_size)
	if verbose:
		print 'creating',path,'size',size
	with open(path, 'wb') as f:
		# TODO: make this more efficient.
		while size:
			f.write(chr(random.randint(0,255)))
			size -= 1


def create_test_dir(root, num_files, branch_factor, max_size, verbose=False):
	levels = int(math.ceil(math.log(num_files, branch_factor)))
	formatlen = int(math.ceil(math.log(branch_factor, 16)))
	path_counter = [0] * levels
	remaining = num_files
	while remaining:
		path = root
		path_parts = ['%0*x'%(formatlen,n) for n in path_counter]
		if verbose >= 2:
			print path_parts
		for part in path_parts[:-1]:
			path = os.path.join(path, part)
			if not os.path.exists(path):
				if verbose:
					print 'mkdir', path
				os.mkdir(path)
		path = os.path.join(path, path_parts[-1])
		create_test_file(path, max_size, verbose=verbose)

		inc_level = -1
		while path_counter[inc_level] == branch_factor - 1:
			path_counter[inc_level] = 0
			inc_level -= 1
		path_counter[inc_level] += 1
		remaining -= 1
		if verbose >= 2:
			print remaining, path_counter


def create(args):
	start_path = os.getcwd()
	create_test_dir(start_path, args.files, args.branch_factor, args.max_size, verbose=args.verbose)


def main():
	parser = argparse.ArgumentParser(description='Create test data and run cfv benchmarks.')

	parser.add_argument('-v', '--verbose', action='count')

	subparsers = parser.add_subparsers()

	create_parser = subparsers.add_parser('create', help='create test data hierarchy')
	create_parser.add_argument('--files', type=human_int, help='total number of files to create')
	create_parser.add_argument('--branch-factor', type=human_int, help='(max) number of files or directories at each level')
	create_parser.add_argument('--max-size', type=human_int, help='max file size')
	#create_parser.add_argument('--num-links', type=human_int, help='number of hardlinks per file')
	create_parser.set_defaults(func=create)

	args = parser.parse_args()
	args.func(args)


if __name__ == '__main__':
	main()

