




if __name__=="__main__":

    #Will need to eventually convert this to bed files
    lines = open("../coverage.txt",'r').readlines()
    for p in range(0,len(lines)):
        line = lines[p].rstrip()
        tabs = line.split("\t")
        for i in range(0,len(tabs)):
            sample_out = open("../samples/sample"+str(i),'a')
            depth = int(tabs[i])
            if(depth>0):
                #print p
                out_line = "%d\t%d\n"%(p+1,int(tabs[i]))
                sample_out.write(out_line)
        total_depth = sum([int(t) for t in tabs])
        sample_out = open("../samples/total",'a')
        if(total_depth>0):
            out_line = "%d\t%d\n"%(p+1,total_depth)
            sample_out.write(out_line)

