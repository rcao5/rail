'''
aggr_path.py
(after hmm.py)

Collects the list of states from hmm and bins them into separate files according to permutation and sample

Tab-delimited output tuple columns:
 1. Reference ID
 2. Reference offset (0-based)
 3. Length of run of positions with this state
 4. HMM state
 5. Dataset id (0 for test, >0 for permutations)

Other files:
 Sample files specified by permutation number
 1. Reference ID
 2. Reference start position
 3. Reference end position
 4. HMM state

'''
import os
import sys
import argparse
import time
import pipes
import subprocess, shlex
timeSt = time.clock()

parser = argparse.ArgumentParser(description=\
    'Takes per-position counts for given samples and calculates a summary '
    'statistic such as median or 75% percentile.')
parser.add_argument(\
    '--out_dir', type=str, required=False, default="",
    help='The directory where all of the coverage vectors for each sample will be stored')
parser.add_argument(\
    '--hadoop_exe', type=str, required=False, default="",
    help='The location of the hadoop executable.')

args = parser.parse_args()

if args.hadoop_exe!="":
    fname = "%s/temp_file"%(args.out_dir)  #temp file used to make a global file handle
    print >>sys.stderr,fname
    proc = subprocess.Popen([args.hadoop_exe, 'fs', '-put', '-', fname ], stdin=subprocess.PIPE)
    proc.stdin.close()
    proc.wait()
else:
    fname = "%s/temp_file"%(args.out_dir)  #temp file used to make a global file handle
    print >>sys.stderr,fname
    samp_out = open(fname,'w')

last_perm = -1                 #last permutation id


for ln in sys.stdin:
    ln = ln.rstrip()
    toks = ln.split('\t')
    assert len(toks)==5
    data_id, ref_id, ref_off, ref_len, hmm_st = toks[0], toks[1], int(toks[2]), int(toks[3]), int(toks[4])

    #This is for hadoop mode
    if args.hadoop_exe!="" and (last_perm==-1 or last_perm!=data_id): #initialize pipes
        proc.stdin.close()
        proc.wait()
        out_fname = "%s/perm%s.bed"%(args.out_dir,data_id)
        proc = subprocess.Popen([args.hadoop_exe, 'fs', 'put', '-',out_fname],stdin=subprocess.PIPE)
        line = "%s\t%d\t%d\t%d"%(ref_id,ref_off,ref_off+ref_len,hmm_st)
        proc.stdin.write(line)
        last_perm=data_id
    elif args.hadoop_exe!="" and last_perm==data_id:
        line = "%s\t%d\t%d\t%d"%(ref_id,ref_off,ref_off+ref_len,hmm_st)
        proc.stdin.write(line)
        last_perm=data_id

    #This is for local mode
    if args.hadoop_exe=="" and (last_perm==-1 or last_perm!=data_id): #initialize pipes
        samp_out.close()
        out_fname = "%s/perm%s.bed"%(args.out_dir,data_id)
        line = "%s\t%d\t%d\t%d\n"%(ref_id,ref_off,ref_off+ref_len,hmm_st)
        samp_out = open(out_fname,'w')
        samp_out.write(line)
        last_perm=data_id
    elif args.hadoop_exe=="" and last_perm==data_id:
        line = "%s\t%d\t%d\t%d\n"%(ref_id,ref_off,ref_off+ref_len,hmm_st)
        samp_out.write(line)
        last_perm=data_id

#Done
timeEn = time.clock()
print >>sys.stderr, "DONE with aggr_states.py; time=%0.3f secs" % (timeEn-timeSt)

    
