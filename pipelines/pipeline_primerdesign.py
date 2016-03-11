################################################################################
#
#   MRC FGU Computational Genomics Group
#
#   $Id: pipeline_snps.py 2870 2010-03-03 10:20:29Z andreas $
#
#   Copyright (C) 2009 Andreas Heger
#
#   This program is free software; you can redistribute it and/or
#   modify it under the terms of the GNU General Public License
#   as published by the Free Software Foundation; either version 2
#   of the License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software
#   Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#################################################################################
"""
====================================
Pipeline pipeline_immunogenicity.py
====================================

:Author: Nick Ilott
:Release: $Id$
:Date: |today|
:Tags: Python


Overview
========

This pipeline uses the commandline version of primer3 to design primers for a set of sequences.

Usage
=====

See :ref:`PipelineSettingUp` and :ref:`PipelineRunning` on general information how to use CGAT pipelines.

Configuration
-------------

The pipeline requires a configured :file:`pipeline.ini` file. 

Input
-----

Input is a fasta file that contains all sequences for a genome. For example it may be a fasta file of
cDNA sequences from an organism. Primers will be designed based on a second input file of identifiers
that match those of a subset of the records in the input fasta file. This second input file must be 
called "identifiers.tsv". The reason for including the entire fasta file is to check for specifity of the primers.


Pipeline output
===============

A set of primers for the sequences of interest.

Glossary
========

.. glossary::


Code
====

"""
from ruffus import *

import sys
import os
import glob
import gzip
import itertools
import collections
import time
import optparse
import shutil
import sqlite3
from rpy2.robjects import r as R
import CGAT.Experiment as E
import CGAT.IOTools as IOTools
import CGAT.Database as Database
import CGAT.FastaIterator as FastaIterator
import numpy as np
from PipelinePrimerDesign import PrimerSet

###################################################
###################################################
###################################################
## Pipeline configuration
###################################################

# load options from the config file
import CGATPipelines.Pipeline as P
P.getParameters( 
    [ "pipeline.ini" ] )

PARAMS = P.PARAMS


###################################################
###################################################
###################################################

def readIdentifiers(identifiers):
    '''
    return list of identifiers from file
    '''
    ids = [x[:-1] for x in IOTools.openFile(identifiers).readlines()]
    return ids

###################################################
###################################################
###################################################

@follows(mkdir("mispriming.dir"))
@transform("*.fa.gz",
           regex("(\S+).fa.gz"),
           add_inputs("identifiers.tsv"),
           r"mispriming.dir/\1.mispriming.lib")
def buildMisprimingLib(infiles, outfile):
    '''
    build fasta file of sequences to check for mispriming
    '''
    fasta, identifiers = infiles
    inf = IOTools.openFile(fasta)
    
    E.info("reading ids for sequences to keep")
    ids = readIdentifiers(identifiers)

    outf = IOTools.openFile(outfile, "w")
    E.info("collecting sequences")
    for f in FastaIterator.iterate(IOTools.openFile(fasta)):
        if f.title not in ids:
            outf.write(">%s\n%s\n" % (f.title, f.sequence))
    outf.close()
    

###################################################
###################################################
###################################################


@follows(mkdir("input.dir"), buildMisprimingLib)
@split("*.fa.gz", 
       r"input.dir/*.input")
def buildInputFiles(infile, outfiles):
    '''
    build input file based on parameters and fasta sequences
    that primers are to be designed for
    '''
    PARAMS["constraints_primer_mispriming_library"] = glob.glob("mispriming.dir/*.lib")[0]

    fasta, identifiers = infile[0], "identifiers.tsv"
    inf = IOTools.openFile(fasta)
    
    E.info("Reading ids for primer design")
    ids = readIdentifiers(identifiers)
    
    E.info("collecting sequences")
    for f in FastaIterator.iterate(IOTools.openFile(fasta)):
        if f.title in ids:
            outf = IOTools.openFile(os.path.join(
                "input.dir",f.title.replace(" ", "_") + ".input").replace('"', ''), "w")
            seq = f.sequence
            outf.write("PRIMER_SEQUENCE_ID=%s\n" % f.title)
            for key, value in PARAMS.iteritems():
                if "constraints" in key:
                    outf.write("%s=%s\n" % (key.replace("constraints_", "").upper(), value))
            outf.write("SEQUENCE=%s\n=\n" % seq)
            outf.close()


###################################################
###################################################
###################################################


@follows(mkdir("primers.dir"))
@transform(buildInputFiles, regex("(\S+)/(\S+).input"), r"primers.dir/\2.primers")
def designPrimers(infile, outfile):
    '''
    design primers with primer3
    '''
    statement = '''primer3_core -format_output < %(infile)s > %(outfile)s'''
    P.run()


###################################################
###################################################
###################################################


@follows(mkdir("optimal_primer.dir"))
@merge(designPrimers, "optimal_primer.dir/optimal_primers.tsv")
def buildOptimalPrimerSet(infiles, outfile):
    '''
    build a set of optimal primer pairs across sequences
    '''
    outf = IOTools.openFile(outfile, "w")
    outf.write("""name\tforward_seq\tforward_gc (%) \tforward_tm\tforward_length (bp)\treverse_seq\treverse_gc (%)\treverse_tm\treverse_length (bp)\tfragment_length (bp)\n""")
    for infile in infiles:
        primerset = PrimerSet()
        name = primerset.readName(infile)
        size = primerset.readSize(infile)
        forward = primerset.readForward(infile)
        reverse = primerset.readReverse(infile)
        primerset = primerset.parse(name, size, *forward+reverse)
        outf.write("\t".join([primerset.name, 
                              primerset.forwardseq, 
                              primerset.forwardgc, 
                              primerset.forwardtm,
                              primerset.forwardlength,
                              primerset.reverseseq,
                              primerset.reversegc, 
                              primerset.reversetm, 
                              primerset.reverselength,
                              primerset.size]) + "\n")
    outf.close()


if __name__== "__main__":
    sys.exit( P.main(sys.argv) )    
