#!/usr/bin/env python
"""
create_single_sample_sim_commands.py

Selects 20 simulated GEUVADIS samples at random and constructs commands for
executing simulations with them using run_single_sample_sim.sh. Writes final
commands to stdout.

The default values of all command-line parameters were the ones we used.
Run python create_single_sample_sim_commands.py -h to see what they were and 
whether they should be changed. Four commands are executed at a time.
"""
import random
import sys
import os

if __name__ == '__main__':
    import argparse
    # Print file's docstring if -h is invoked
    parser = argparse.ArgumentParser(description=__doc__, 
            formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--num-processes', type=int, required=False,
        default=8,
        help='Number of threads each aligner should use')
    parser.add_argument('--output-dir', type=str, required=False,
        default='/scratch0/langmead-fs1/geuvadis_sims_for_paper_v2/8core',
        help='Directory to which output of all simulations should be written ')
    parser.add_argument('--data-dir', type=str, required=False,
        default='/scratch0/langmead-fs1/geuvadis_sims_for_paper_v2',
        help='Where to find Flux FASTQs and BEDs output by '
             'generate_bioreps.py')
    parser.add_argument('--scratch', type=str, required=False,
        default='/tmp',
        help='Scratch directory. If running each command on cluster, make '
             'this a node-local directory.')
    parser.add_argument('--aligners', type=str, required=True,
        nargs='+',
        help=('aligner to use to run simulation; assumes script in dir is '
              'present in format run_single_sample_[aligner]_sim.sh'))
    args = parser.parse_args()
    sample_names = []
    with open(
            os.path.join(os.path.dirname(__file__), 'GEUVADIS_112.manifest')
        ) as manifest_stream:
        sample_names = [line.strip().split('\t')[-1]
                        for line in manifest_stream
                        if line[0] != '#' and line.strip()]
    random.seed(1)
    final_sample_names = random.sample(sample_names, 20)
    total_counter = 0
    for aligner in args.aligners:
        script_path = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                    'run_single_sample_'
                                    + aligner + '_sim.sh')
        for sample_name in final_sample_names:
            #if total_counter and (total_counter % 4) == 0:
            #    print 'wait'
            print 'sh {} {} {} {} {} {}'.format(
                    script_path,
                    args.num_processes,
                    args.output_dir,
                    args.data_dir,
                    sample_name,
                    args.scratch
                )
            total_counter += 1