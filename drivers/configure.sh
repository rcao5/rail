##Modify the parameters below
NTASKS=20
HMM_OVERLAP=30
PERMUTATIONS=5
READLET_LEN=30
READLET_IVAL=5
IGENOME="/damsl/projects/myrna2/langmead/igenomes/Homo_sapiens/UCSC/hg19"
RNASEQ="/damsl/projects/myrna2/langmead/tornado/data/trapnell/"
MANIFEST="/damsl/projects/myrna2/software/tornado/example/sim_human/human.manifest"
INTERMEDIATE_DIR="/damsl/projects/myrna2/software/tornado/example/sim_human/intermediate"
HDFS_DIR="/user/hduser/sim_human"
MODE="hadoop"      #Note: make sure that HADOOP_HOME are already set in .bashrc

#Don't modify anything below here!!!
if [ "hadoop" = "$MODE" ]; then
    echo 'HADOOP_FILES='$HDFS_DIR'' > run.sh
    python gen_script.py --ntasks=$NTASKS --hmm_overlap=$HMM_OVERLAP --permutations=$PERMUTATIONS --readlet_len=$READLET_LEN --readlet_ival=$READLET_IVAL --igenome=$IGENOME --rnaseq=$RNASEQ --manifest=$MANIFEST --intermediate=$INTERMEDIATE_DIR >> run.sh
    cat hadoop_base.sh >> run.sh
    chmod +x run.sh
elif [ "local" = "$MODE" ]; then
    python gen_script.py --ntasks=$NTASKS --hmm_overlap=$HMM_OVERLAP --permutations=$PERMUTATIONS --readlet_len=$READLET_LEN --readlet_ival=$READLET_IVAL --igenome=$IGENOME --rnaseq=$RNASEQ --manifest=$MANIFEST --intermediate=$INTERMEDIATE_DIR> run.sh
    cat local_base.sh >> run.sh
    chmod +x run.sh
else
    echo "That option doesn't exist!"
fi