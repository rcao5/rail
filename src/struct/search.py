"""
search.py
Various ways to conduct a binary search on a sorted list

Copied from http://docs.python.org/2/library/bisect.html
"""
import bisect
import sys
import unittest
import random
import string

"""
Find an element out of a list of tuples with form
(pos1,pos2,chromosome,transcript_id)
"""
def find_tuple(tups,x):
    pos1,pos2,seqids,_ = zip(*tups)
    xpos1,xpos2,xseqid,_ = x
    #Narrow down search based on chromosome
    left_i  = bisect.bisect_left(seqids,xseqid)
    right_i = bisect.bisect_right(seqids,xseqid)
    i = bisect.bisect_left(pos1[left_i:right_i],xpos1)
    diff = right_i-left_i
    if i > 0 and i<diff:
        return tups[left_i+i-1] if abs(tups[i-1][0]-x[0])< abs(tups[i][0]-x[0]) else tups[left_i+i]
    else:
        if i==0:
            return tups[left_i]
        else:
            return tups[left_i+diff-1]

def find(a,x):
    'Find the closest value to x'
    i = bisect.bisect_left(a,x)
    if i > 0 and i<len(a):
        return a[i-1] if abs(a[i-1]-x)< abs(a[i]-x) else a[i]
    else:
        if i==0:
            return a[i]
        elif i==len(a):
            return a[i-1]
        else:
            print >> sys.stderr,"Index not found",i
            return -100000000
"""
Binary search methods on lists
"""
def index(a, x):
    'Locate the leftmost value exactly equal to x'
    i = bisect.bisect_left(a, x)
    if i != len(a) and a[i] == x:
        return i
    raise ValueError

def find_lt(a, x):
    'Find rightmost value less than x'
    i = bisect.bisect_left(a, x)
    if i:
        return a[i-1]
    raise ValueError

def find_ge(a, x):
    'Find leftmost item greater than or equal to x'
    i = bisect.bisect_left(a, x)
    if i != len(a):
        return a[i]
    raise ValueError

def find_le(a, x):
    'Find rightmost value less than or equal to x'
    i = bisect.bisect_right(a, x)
    if i:
        return a[i-1]
    raise ValueError

def find_gt(a, x):
    'Find leftmost value greater than x'
    i = bisect.bisect_right(a, x)
    if i != len(a):
        return a[i]
    raise ValueError

class TestSearchFunctions(unittest.TestCase):
    def setUp(self):
        N = 10
        R = 1
        pos1 = range(N)
        pos2 = range(N)
        seqids = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(R))
        xscript_ids = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(R))
        self.tups = zip(pos1,pos2,seqids,xscript_ids)

    def test_search1(self):
        element = random.choice(self.tups)
        self.assertTrue(element in self.tups)
        result = find_tuple(self.tups,element)
        self.assertTrue(result==element)

    def test_search2(self):
        element = random.choice(self.tups)
        self.assertTrue(element in self.tups)
        element = (element[0]+1,element[1]+1,element[2],element[3])
        result = find_tuple(self.tups,element)
        self.assertTrue(result[0]+1==element[0] and result[1]+1==element[1])


if __name__=='__main__':
    unittest.main()
