![Rail-RNA logo](https://github.com/nellore/rail/blob/master/assets/railrnalogodark.png)
====

This is the official repo for Rail-RNA, software for RNA-seq analysis. [Download](https://github.com/nellore/rail/raw/v0.1.7a/releases/install_rail-rna-0.1.7a) the latest stable release. **Ask questions in the repo's Gitter: [![Join the chat at https://gitter.im/nellore/rail](https://badges.gitter.im/Join%20Chat.svg)](https://gitter.im/nellore/rail?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge) .**

Get interested
-----
Rail-RNA's distinguishing features are
* **Scalability**. Built on MapReduce, the software scales to analyze hundreds of RNA-seq samples at the same time.
* **Reduced redundancy**. The software identifies and eliminates redundant alignment work, making the end-to-end analysis time per sample *decrease* for fixed computer cluster size as the number of samples increases.
* **Integrative analysis**. The software borrows strength across replicates to achieve more accurate splice junction detection, especially in genomic regions with low coverage.
* **Mode agnosticism**. The software integrates its own parallel abstraction layer that allows it to be run in various distributed computing environments, including the Amazon Web Services (AWS) [Elastic MapReduce (EMR) service](http://aws.amazon.com/elasticmapreduce/), or any distributed environment supported by [IPython](http://ipython.org/), including clusters using batch schedulers like PBS or SGE, Message Passing Interface (MPI), or any cluster with a shared filesystem and mutual SSH access. Alternately, Rail-RNA can be run on a single multi-core computer, without the aid of a batch system or MapReduce implementation.
* **Inexpensive cloud implementation**. An EMR run on > ~100 samples costs < $1/sample with spot instances.

Outputs currently include
* Alignment BAMs with only primary alignments by default (for more, use `--bowtie2-args "-k <N>"`, where `<N>` is the maximum number of alignments to report per read)
* Genome coverage bigWigs
* [TopHat](http://ccb.jhu.edu/software/tophat/index.shtml)-like indel and splice junction BEDs

and will likely expand in future versions.

Read the [preprint](http://biorxiv.org/content/early/2015/05/07/019067) for more details. Methods explained there correspond to Rail-RNA 0.1.0a.

Get set up
-----
Start with a recent (>= 2009) Mac OS or Linux box. Download [`install_rail-rna-0.1.7a`](https://github.com/nellore/rail/raw/v0.1.6c/releases/install_rail-rna-0.1.7a), change to the directory containing it, and make the installer executable with
```
chmod +x install_rail-rna-0.1.7a
```
Now run
```
sudo ./install_rail-rna-0.1.7a
```
to install for all users or
```
./install_rail-rna-0.1.7a
```
to install for just you. Check
```
./install_rail-rna-0.1.7a -h
```
for more installation options. If the executable doesn't work, you may need [Python](http://www.python.org). You'll also need Bowtie 1 and 2 indexes of the appropriate genome assembly if you will be running Rail-RNA in either its single-computer (local) or IPython Parallel (parallel) modes. The easiest way to get these is by downloading an [Illumina iGenome](http://support.illumina.com/sequencing/sequencing_software/igenome.html). If running Rail-RNA on EMR (elastic mode) and aligning to hg19, the assembly can be specified at the command line with the `-a` parameter. More assemblies are on their way.

Get started
-----
Rail-RNA takes as input a [Myrna](http://bowtie-bio.sourceforge.net/myrna/)-style manifest file, which describes a set of input FASTQs that may be on the local filesystem in local and parallel modes; or on the web or Amazon [Simple Storage Service](http://aws.amazon.com/s3/) (S3) in local, parallel, and elastic modes. Each line takes one of the following two forms.

1. (for a set of unpaired input reads) `<FASTQ URL>(tab)<optional MD5>(tab)<sample label>`
2. (for a set of paired input reads) `<FASTQ URL 1>(tab)<optional MD5 1>(tab)<FASTQ URL 2>(tab)<optional MD5 2>(tab)<sample label>`

`<sample label>` must be formatted as `<group ID>-<biorep ID>-<techrep ID>`.

**Find some RNA-seq data, create a manifest file, run**
```
rail-rna
```
**and follow the instructions.** A manual will be posted shortly.

To use Rail-RNA in elastic mode, you'll need an account with [AWS](http://aws.amazon.com/). For an introduction to cloud computing with AWS, refer to [this](https://github.com/griffithlab/rnaseq_tutorial/wiki/Intro-to-AWS-Cloud-Computing) excellent tutorial by the [Griffith Lab](http://genome.wustl.edu/people/groups/detail/griffith-lab/) at Wash U.

Disclaimer
-----
Renting AWS resources costs money, regardless of whether your run ultimately succeeds or fails. In some cases, Rail-RNA or its documentation may be partially to blame for a failed run. While we are happy to review bug reports, we do not accept responsibility for financial damage caused by these errors. Rail-RNA is provided "as is" with no warranty.

Licenses
-----
[GNU GPL v3.0](http://choosealicense.com/licenses/gpl-3.0/) unless otherwise specified. [Dooplicity](https://github.com/nellore/rail/tree/master/src/dooplicity), for example, is [MIT-licensed](http://choosealicense.com/licenses/mit/).

Contributors
-----
* [Abhi Nellore]
* [Leo Collado-Torres]
* [Andrew Jaffe]
* [Jamie Morton]
* [Jacob Pritt]
* [José Alquicira-Hernández]
* [Jeff Leek]
* [Ben Langmead]

[Abhi Nellore]: http://nellore.github.io/
[Leo Collado-Torres]: http://www.biostat.jhsph.edu/~lcollado/
[Andrew Jaffe]: http://www.aejaffe.com/
[Jamie Morton]: https://github.com/mortonjt
[Jacob Pritt]: https://github.com/jpritt
[José Alquicira-Hernández]: https://github.com/joseah
[Ben Langmead]: http://www.langmead-lab.org/
[Jeff Leek]: http://jtleek.com/

This product was developed primarily at

<a href="http://www.jhu.edu/"><img src="https://github.com/nellore/rail/blob/master/assets/university.logo.small.horizontal.blue.png" align="left" width="300" alt="Hopkins logo"></a>
