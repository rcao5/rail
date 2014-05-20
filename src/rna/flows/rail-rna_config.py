"""
rail-rna_config.py
Part of Rail-RNA

Contains classes that perform error checking and generate JSON configuration
output for Rail-RNA. These configurations are parsable by Dooplicity's
hadoop_simulator.py and emr_runner.py.

Class structure is designed so only those arguments relevant to modes/job flows
are included.

The descriptions of command-line arguments contained here assume that a
calling script has the command-line options "--local", "--cloud",
"--preprocess", "--align", and "--all".

TO PUT IN rail-rna.py:

modes = set(['local', 'cloud'])
        # Implement Hadoop mode after paper submission
        if mode not in modes:
            self.errors.append('Mode ("--mode") must be one of '
                               '{{"local", "cloud"}}, but {0} was '
                               'entered.'.format(mode))
        self.mode = mode
        job_flows = set(['preprocess', 'align', 'all'])
        if job_flow not in job_flows:
            self.errors.append('Job flow ("--job-flows") must be one of '
                               '{{"preprocess", "align", "all"}}, but {0} was '
                               'entered.'.format(mode))
"""

import os
base_path = os.path.abspath(
                    os.path.dirname(os.path.dirname(os.path.dirname(
                        os.path.realpath(__file__)))
                    )
                )
utils_path = os.path.join(base_path, 'rna', 'utils')
import site
site.addsitedir(utils_path)
site.addsitedir(base_path)
import dooplicity.ansibles as ab
import tempfile
import shutil
from dooplicity.tools import which, is_exe, path_join
from argparse import SUPPRESS

def step(name, inputs, output, mapper='cat', reducer='cat', 
    action_on_failure='TERMINATE_JOB_FLOW',
    jar='/home/hadoop/contrib/streaming/hadoop-streaming-1.0.3.jar',
    tasks=0, partitioner_options=None, key_fields=None, archives=None,
    multiple_outputs=False, inputformat=None):
    """ Outputs JSON for a given step.

        name: name of step
        inputs: list of input directories/files
        output: output directory
        mapper: mapper command
        reducer: reducer command
        jar: path to Hadoop Streaming jar; ignored in local mode
        tasks: reduce task count
        partitioner options: UNIX sort-like partitioner options
        key fields: number of key fields,
        archives: -archives option
        multiple_outputs: True iff there are multiple outputs; else False
        inputformat: -inputformat option

        Return value: step dictionary
    """
    to_return = {
        'Name' : name,
        'ActionOnFailure' : action_on_failure,
        'HadoopJarStep' : {
            'Jar' : jar,
            'Args' : []
        }

    }
    to_return.extend(['-D', 'mapred.reduce.tasks=%d' % tasks])
    if partioner_options is not None and key_fields is not None:
        to_return['HadoopJarStep']['Args'].extend([
                '-D', 'mapred.text.key.partitioner.options=-%s'
                            % partitioner_options,
                '-D', 'stream.num.map.output.key.fields=%d' % key_fields
            ])
    if multiple_outputs:
        # This only matters in cloud mode
        to_return['HadoopJarStep']['Args'].extend([
            '-libjars', '/mnt/lib/multiplefiles.jar'
        ])
    if archives is not None:
        to_return['HadoopJarStep']['Args'].extend([
                '-archives', archives
            ])
    to_return['HadoopJarStep']['Args'].extend([
            '-partitioner',
            'org.apache.hadoop.mapred.lib.KeyFieldBasedPartitioner',
        ])
    for an_input in inputs:
        to_return['HadoopJarStep']['Args'].extend([
                '-input', an_input.strip()
            ])
    to_return['HadoopJarStep']['Args'].extend([
            '-output', output,
            '-mapper', mapper,
            '-reducer', reducer
        ])
    if multiple_outputs:
        to_return.extend([
                '-outputformat', 'edu.jhu.cs.MultipleOutputFormat'
            ])
    if input_format is not None:
        to_return.extend([
                '-intputformat', inputformat
            ])
    return to_return

def steps(protosteps, action_on_failure, jar, step_dir, 
            reducer_count, intermediate_dir, unix=False):
    """ Turns list with "protosteps" into well-formed StepConfig list.

        A protostep looks like this:

            {
                'name' : [name of step]
                'run' : Python script name; like 'preprocess.py' + args
                'inputs' : list of input directories
                'no_input_prefix' : key that's present iff intermediate dir
                    should not be prepended to inputs
                'output' : output directory
                'no_output_prefix' : key that's present iff intermediate dir
                    should not be prepended to output dir
                'keys'  : Number of key fields; present only if reducer
                'part'  : KeyFieldBasedPartitioner options; present only if
                            reducer
                'taskx' : number of tasks per reducer or None if total number
                    of tasks should be 1
                'inputformat' : input format; present only if necessary
                'archives' : archives parameter; present only if necessary
                'multiple_outputs' : key that's present iff there are multiple
                    outputs
            }

        protosteps: array of protosteps
        action_on_failure: action on failure to take
        jar: path to Hadoop Streaming jar
        step_dir: where to find Python scripts for steps
        reducer_count: number of reducers; determines number of tasks
        unix: performs UNIX-like path joins; also inserts pypy in for
            executable since unix=True only on EMR

        Return value: list of StepConfigs (see Elastic MapReduce API docs)
    """
    true_steps = []
    for protostep in protosteps:
        assert ('keys' in protostep and 'part' in protostep) or \
                ('keys' not in protostep and 'part' not in protostep)
        true_steps.append(step(
                            name=protostep['name'],
                            inputs=([path_join(unix, intermediate_dir,
                                        an_input) for an_input in
                                        protostep['inputs']]
                                    if 'no_input_prefix' not in
                                    protostep else protostep['inputs']),
                            output=(path_join(unix, intermediate_dir,
                                                    protostep['output'])
                                    if 'no_output_prefix' not in
                                    protostep else protostep['output']),
                            mapper=(path_join(unix, 'pypy' if unix
                                    else sys.executable, step_dir,
                                                    protostep['run'])
                                    if 'keys' not in protostep
                                    else 'cat'),
                            reducer=(path_join(unix, 'pypy' if unix
                                     else sys.executable, step_dir,
                                                    protostep['run'])
                                    if 'keys' in protostep
                                    else 'cat'),
                            action_on_failure=action_on_failure,
                            jar=jar,
                            tasks=(reducer_count * protostep['taskx']
                                    if protostep['taskx'] is not None
                                    else 1),
                            partitioner_options=(protostep['part']
                                if 'part' in protostep else None),
                            key_fields=(protostep['keys']
                                if 'keys' in protostep else None),
                            archives=(protostep['archives']
                                if 'archives' in protostep else None),
                            multiple_outputs=(True if 'multiple_outputs'
                                    in protostep else False
                                ),
                            inputformat=(protostep['inputformat']
                                if 'inputformat' in protostep else None)
                        )
                    )
    return true_steps

class RailRnaErrors:
    """ Holds accumulated errors in Rail-RNA's input parameters.

        Checks only those parameters common to all modes/job flows.
    """
    def __init__(self, manifest, output_dir,
            intermediate_dir='./intermediate', force=False, aws_exe=None,
            profile='default', region='us-east-1', verbose=False
        ):
        '''Store all errors uncovered in a list, then output. This prevents the
        user from having to rerun Rail-RNA to find what else is wrong with
        the command-line parameters.'''
        self.errors = []
        self.manifest_dir = None
        self.manifest = manifest
        self.output_dir = output_dir
        self.intermediate_dir = intermediate_dir
        self.aws_exe = aws_exe
        self.region = region
        self.force = force
        self.checked_programs = set()
        self.curl_exe = curl_exe
        self.verbose = verbose

    def check_s3(self, reason=None):
        """ Checks for AWS CLI and configuration file.

            In this script, S3 checking is performed as soon as it is found
            that S3 is needed. If anything is awry, a RuntimeError is raised
            _immediately_ (the standard behavior is to raise a RuntimeError
            only after errors are accumulated). A reason specifying where
            S3 credentials were first needed can also be provided.

            reason: string specifying where S3 credentials were first
                needed.

            No return value.
        """
        original_errors_size = len(self.errors)
        if aws_exe is None:
            self.aws_exe = 'aws'
            if not which(self.aws_exe):
                self.errors.append(('The AWS CLI executable '
                                    'was not found. Make sure that the '
                                    'executable is in PATH, or specify the '
                                    'location of the executable with '
                                    '"--aws-exe".'))
            else:
                self.errors.append(('The AWS CLI executable ("--aws-exe") '
                                    '"{0}" was not found. Make sure that '
                                    'the file is present and is '
                                    'executable.').format(aws_exe))
        elif not is_exe(self.aws_exe):
            self.errors.append(('The AWS CLI executable ("--aws-exe") '
                                '"{0}" is either not present or not '
                                'executable.').format(aws_exe))
        self._aws_access_key_id = None
        self._aws_secret_access_key = None
        if profile == 'default':
            # Search environment variables for keys first if profile is default
            try:
                self._aws_access_key_id = os.environ['AWS_ACCESS_KEY_ID']
                self._aws_secret_access_key \
                    = os.environ['AWS_SECRET_ACCESS_KEY']
                to_search = None
            except KeyError:
                to_search = '[default]'
            try:
                # Also grab region
                self.region = os.environ['AWS_DEFAULT_REGION']
            except KeyError:
                pass
        else:
            to_search = '[profile ' + profile + ']'
        # Now search AWS CLI config file for the right profile
        if to_search is not None:
            config_file = os.path.join(os.environ['HOME'], '.aws', 'config')
            try:
                with open(config_file) as config_stream:
                    for line in config_stream:
                        if line.strip() == to_search:
                            break
                    for line in config_stream:
                        tokens = [token.strip() for token in line.split('=')]
                        if tokens[0] == 'region' \
                            and self.region == 'us-east-1':
                            self.region = tokens[1]
                        elif tokens[0] == 'aws_access_key_id':
                            self._aws_access_key_id = tokens[1]
                        elif tokens[0] == 'aws_secret_access_key':
                            self._aws_secret_access_key = tokens[1]
                        else:
                            line = line.strip()
                            if line[0] == '[' and line[-1] == ']':
                                # Break on start of new profile
                                break
            except IOError:
                self.errors.append(
                                   ('No valid AWS CLI configuration found. '
                                    'Make sure the AWS CLI is installed '
                                    'properly and that one of the following '
                                    'is true:\n\na) The environment variables '
                                    '"AWS_ACCESS_KEY_ID" and '
                                    '"AWS_SECRET_ACCESS_KEY" are set to '
                                    'the desired AWS access key ID and '
                                    'secret access key, respectively, and '
                                    'the profile ("--profile") is set to '
                                    '"default" (its default value).\n\n'
                                    'b) The file ".aws/config" exists in your '
                                    'home directory with a valid profile. '
                                    'To set this file up, run "aws --config" '
                                    'after installing the AWS CLI.')
                                )
        if len(self.errors) != original_errors_size:
            if reason:
                raise RuntimeError(('\n'.join(['%d) %s' % (i, error)
                                    for i, error
                                    in enumerate(self.errors)]) + 
                                    '\n\nNote that the AWS CLI is needed '
                                    'because {0}. If all dependence on S3 in '
                                    'the pipeline is removed, the AWS CLI '
                                    'need not be installed.').format(reason))
            else:
                raise RuntimeError(('\n'.join(['%d) %s' % (i, error)
                                    for i, error
                                    in enumerate(self.errors)]) + 
                                    '\n\nIf all dependence on S3 in the '
                                    'pipeline is removed, the AWS CLI need '
                                    'not be installed.'))
        self.checked_programs.add('AWS CLI')

    def check_program(exe, program_name, parameter,
                        entered_exe=None, reason=None):
        """ Checks if program in PATH or if user specified it properly.

            Errors are added to self.errors.

            exe: executable to search for
            program name: name of program
            parameter: corresponding command line parameter
                (e.g., --bowtie-exe)
            entered_exe: None if the user didn't enter an executable; otherwise
                whatever the user entered
            reason: FOR CURL ONLY: raise RuntimeError _immediately_ if Curl
                not found but needed

            No return value.
        """
        original_errors_size = len(self.errors)
        if entered_exe is None:
            if not which(exe):
                self.errors.append(
                        ('The executable "{0}" for {1} was either not found '
                         'in PATH or is not executable. Check that the '
                         'program is installed properly and executable; then '
                         'either add the executable to PATH or specify it '
                         'directly with "{3}".').format(exe, program_name,
                                                            parameter)
                    )
            else:
                to_return = exe
        elif not is_exe(entered_exe):
            self.errors.append(
                    ('The executable "{0}" entered for {1} via "{2}" was '
                     'either not found or is not executable.').format(exe,
                                                                program_name,
                                                                parameter)
                )
        else:
            to_return = entered_exe
        if original_errors_size != len(self.errors) and reason:
            raise RuntimeError(('\n'.join(['%d) %s' % (i, error)
                                for i, error
                                in enumerate(self.errors)]) + 
                                '\n\nNote that Curl is needed because {0}.'
                                ' If all dependence on web resources is '
                                'removed from the pipeline, Curl need '
                                'not be installed.').format(reason))
        self.checked_programs.add(program_name)
        return to_return

    @staticmethod
    def add_args(parser):
        parser.add_argument(
            '--aws-exe', type=str, required=False,
            default=None,
            help=('AWS CLI executable. If "aws" is in PATH, this parameter '
                 'should be left unspecified. If it\'s not, the full path to '
                 'the executable should be specified. If S3 is never used in '
                 'a given job flow, this parameter is inconsequential.')
        )
        parser.add_argument(
            '--curl-exe', type=str, required=False,
            default=None,
            help=('Curl executable. If "curl" is in PATH, this parameter '
                  'should be left unspecified. If it\'s not, the full path to '
                  'the executable should be specified.')
        )
        parser.add_argument(
            '--profile', type=str, required=False,
            default=None,
            help=('AWS CLI profile to use. Defaults to [default]; if, '
                  'however, the environment variables "AWS_ACCESS_KEY_ID", '
                  'and "AWS_SECRET_ACCESS_KEY" are set, these are used '
                  'instead of [default].')
        )
        parser.add_argument(
            '-f', '--force', action='store_const', const=True,
            default=False,
            help='Overwrites output directory if it exists.'
        )
        '''--region's help looks different from mode to mode; don't include it
        here.'''

class RailRnaLocal:
    """ Checks local-mode JSON from input parameters and relevant programs.

        Subsumes only those parameters relevant to local mode. Adds errors
        to base instance of RailRnaErrors.
    """
    def __init__(self, base, check_manifest=False,
                    num_processes=1, keep_intermediates=False):
        """ base: instance of RailRnaErrors """
        # Initialize ansible for easy checks
        ansible = ab.Ansible()
        if not ab.Url(base,intermediate_dir).is_local:
            base.errors.append(('Intermediate directory must be local '
                                'when running Rail-RNA in local ("--local") '
                                'mode, but {0} was entered.').format(
                                        base.intermediate_dir
                                    ))
        output_dir_url = ab.Url(base.output_dir)
        if output_dir_url.is_curlable:
            base.errors.append(('Output directory must be local or on S3 '
                                'when running Rail-RNA in local ("--local") '
                                'mode, but {0} was entered.').format(
                                        base.output_dir
                                    ))
        elif output_dir_url.is_s3 and 'AWS CLI' not in base.checked_programs:
            base.check_s3(reason='the output directory is on S3')
            # Change ansible params
            ansible.aws_exe = base.aws_exe
            ansible.profile = base.profile
        if not base.force:
            if output_dir_url.is_local \
                and os.path.exists(output_dir_url.to_url()):
                base.errors.append(('Output directory {0} exists, '
                                    'and "--force" was not invoked to permit '
                                    'overwriting it.').format(base.output_dir))
            elif output_dir_url.is_s3 \
                and ansible.s3_ansible.is_dir(base.output_dir):
                base.errors.append(('Output directory {0} exists on S3, and '
                                    '"--force" was not invoked to permit '
                                    'overwriting it.').format(base_output_dir))
        # Check manifest; download it if necessary
        manifest_url = ab.Url(base.manifest)
        if manifest_url.is_s3 and 'AWS CLI' not in base.checked_programs:
            base.check_s3(reason='the manifest file is on S3')
            # Change ansible params
            ansible.aws_exe = base.aws_exe
            ansible.profile = base.profile
        elif manifest_url.is_curlable \
            and 'Curl' not in base.checked_programs:
            base.curl_exe = base.check_program('curl', 'Curl', '--curl_exe',
                                    entered_exe=base.curl_exe,
                                    reason='the manifest file is on the web')
            ansible.curl_exe = base.curl_exe
        if not ansible.exists(manifest_url.to_url()):
            base.errors.append(('Manifest file ("--manifest") {0} '
                                'does not exist. Check the URL and '
                                'try again.').format(base.manifest))
        else:
            if not manifest_url.is_local:
                base.manifest_dir = tempfile.mkdtemp()
                base.manifest = os.path.join(base.manifest_dir, 'MANIFEST')
                ansible.get(manifest_url, destination=base.manifest)
            files_to_check = []
            with open(base.manifest) as manifest_stream:
                for line in manifest_stream:
                    tokens = line.strip().split('\t')
                    if len(tokens) == 5:
                        files_to_check.extend([tokens[0], tokens[2]])
                    elif len(tokens) == 3:
                        files_to_check.append(tokens[0])
                    else:
                        base.errors.append(('The following line from the '
                                            'manifest file {0} '
                                            'has an invalid number of '
                                            'tokens:\n{1}'
                                            ).format(
                                                    manifest_url.to_url(),
                                                    line
                                                ))
            if files_to_check:
                if check_manifest:
                    # Check files in manifest only if in preprocess job flow
                    for filename in files_to_check:
                        filename_url = ab.Url(filename)
                        if filename_url.is_s3 \
                            and 'AWS CLI' not in base.checked_programs:
                                base.check_s3(reason=('at least one sample '
                                                      'FASTA/FASTQ from the '
                                                      'manifest file is on '
                                                      'S3'))
                                # Change ansible params
                                ansible.aws_exe = base.aws_exe
                                ansible.profile = base.profile
                        elif filename_url.is_curlable \
                            and 'Curl' not in base.checked_programs:
                            base.curl_exe = base.check_program('curl', 'Curl',
                                                '--curl_exe',
                                                entered_exe=base.curl_exe,
                                                reason=('at least one sample '
                                                  'FASTA/FASTQ from the '
                                                  'manifest file is on '
                                                  'the web'))
                            ansible.curl_exe = base.curl_exe
                        if not ansible.exists(filename_url):
                            base.errors.append(('The file {0} from the '
                                                'manifest file {1} does not '
                                                'exist. Check the URL and try '
                                                'again.').format(
                                                        filename,
                                                        manifest_url.to_url()
                                                    ))
            else:
                base.errors.append(('Manifest file ("--manifest") {0} '
                                    'has no valid lines.').format(
                                                        manifest_url.to_url()
                                                    ))
        from multiprocessing import cpu_count
        if num_processes:
            if not (isinstance(num_processes, int)
                                    and num_processes >= 1):
                base.errors.append('Number of processes ("--num-processes") '
                                   'must be an integer >= 1, '
                                   'but {0} was entered.'.format(
                                                    num_processes
                                                ))
            else:
                base.num_processes = num_processes
        else:
            try:
                base.num_processes = cpu_count()
            except NotImplementedError:
                base.num_processes = 1
            if base.num_processes != 1:
                '''Make default number of processes cpu count less 1
                so Facebook tab in user's browser won't go all unresponsive.'''
                base.num_processes -= 1
        self.keep_intermediates = keep_intermediates

    @staticmethod
    def add_args(parser):
        """ Adds parameter descriptions relevant to local mode to an object
            of class argparse.ArgumentParser.

            No return value.
        """
        parser.add_argument(
            '-m', '--manifest', type=str, required=True,
            help='Myrna-style manifest file listing sample FASTAs and/or ' \
                 'FASTQs to analyze. When running Rail-RNA in local ' \
                 '("--local") mode, this file must be on the local ' \
                 'filesystem. Each line of the file is ' \
                 'is in one of two formats: ' \
                 '\n\n(for unpaired input reads)\n' \
                 '<URL><TAB><MD5 checksum or "0" if not included><TAB>' \
                 '<sample label>' \
                 '\n\n(for paired-end input reads)\n' \
                 '<URL 1><TAB><MD5 checksum or "0" if not included><TAB>' \
                 '<URL 2><TAB><MD5 checksum or "0" if not included><TAB>' \
                 '<sample label>.'
        )
        parser.add_argument(
            '-o', '--output', type=str, required=False,
            default='./rail-rna_out',
            help=('Output directory, which in local ("--local") mode must be '
                  'on the local filesystem or on S3. This directory is not '
                  'overwritten unless the force overwrite ("--force") '
                  'parameter is also invoked.')
        )
        parser.add_argument(
            '--intermediate', type=str, required=False,
            default='./rail-rna_intermediate',
            help='Directory in which to store intermediate files, which ' \
                 'may be useful for debugging. Invoke ' \
                 '"--keep-intermediates" to prevent deletion of ' \
                 'intermediate files after a job flow is completed.'
        )
        parser.add_argument(
            '--num-processes', type=int, required=False,
            default=None,
            help=('Number of processes to run simultaneously. This defaults '
                  'to the number of cores on the machine less 1 if more than '
                  'one core is available, or simply 1 if the program could '
                  'not determine the number of available cores.')
        )
        parser.add_argument(
            '--keep-intermediates', action='store_const', const=True,
            default=False,
            help='Keeps intermediate files after a job flow is completed.'
        )
        parser.add_argument(
            '--verbose', action='store_const', const=True,
            default=False,
            help='Outputs extra debugging statements to stderr.'
        )

class RailRnaCloud:
    """ Checks cloud-mode input parameters and relevant programs.

        Subsumes only those parameters relevant to cloud mode. Adds errors
        to base instance of RailRnaErrors.
    """
    def __init__(self, base, check_manifest=False,
        log_uri=None, ami_version='2.4.2',
        visible_to_all_users=False, tags='',
        name='Rail-RNA Job Flow',
        action_on_failure='TERMINATE_JOB_FLOW',
        hadoop_jar='/home/hadoop/contrib/streaming/hadoop-streaming-1.0.3.jar',
        master_instance_count=1, master_instance_type='c1.xlarge',
        master_instance_bid_price=None, core_instance_count=1,
        core_instance_type=None, core_instance_bid_price=None,
        task_instance_count=0, task_instance_type=None,
        task_instance_bid_price=None, ec2_key_name=None, keep_alive=False,
        termination_protected=False):

        # CLI is REQUIRED in cloud mode
        base.check_s3(reason='Rail-RNA is running in cloud ("--cloud") mode')

        # Initialize possible options
        base.instance_core_counts = {
            "m1.small"    : 1,
            "m1.large"    : 2,
            "m1.xlarge"   : 4,
            "c1.medium"   : 2,
            "c1.xlarge"   : 8,
            "m2.xlarge"   : 2,
            "m2.2xlarge"  : 4,
            "m2.4xlarge"  : 8,
            "cc1.4xlarge" : 8
        }

        base.instance_swap_allocations = {
            "m1.small"    : (2 *1024), #  1.7 GB
            "m1.large"    : (8 *1024), #  7.5 GB
            "m1.xlarge"   : (16*1024), # 15.0 GB
            "c1.medium"   : (2 *1024), #  1.7 GB
            "c1.xlarge"   : (8 *1024), #  7.0 GB
            "m2.xlarge"   : (16*1024), # 17.1 GB
            "m2.2xlarge"  : (16*1024), # 34.2 GB
            "m2.4xlarge"  : (16*1024), # 68.4 GB
            "cc1.4xlarge" : (16*1024)  # 23.0 GB
        }

        '''Not currently in use, but may become important if there are
        32- vs. 64-bit issues: base.instance_bits = {
            "m1.small"    : 32,
            "m1.large"    : 64,
            "m1.xlarge"   : 64,
            "c1.medium"   : 32,
            "c1.xlarge"   : 64,
            "m2.xlarge"   : 64,
            "m2.2xlarge"  : 64,
            "m2.4xlarge"  : 64,
            "cc1.4xlarge" : 64
        }'''

        if log_uri is not None and not Url(log_uri).is_s3:
            base.errors.append('Log URI ("--log-uri") must be on S3, but '
                               '"{0}" was entered.'.format(log_uri))
        base.log_uri = log_uri
        base.visible_to_all_users = visible_to_all_users
        base.tags = str([tag.strip() for tag in tags.split(',')])
        base.name = name

        # Initialize ansible for easy checks
        ansible = ab.Ansible(aws_exe=base.aws_exe, profile=base.profile)
        if ab.Url(base,intermediate_dir).is_local:
            base.errors.append(('Intermediate directory must be on HDFS or S3 '
                                'when running Rail-RNA in cloud ("--cloud") '
                                'mode, but {0} was entered.').format(
                                        base.intermediate_dir
                                    ))
        output_dir_url = ab.Url(base.output_dir)
        if not output_dir_url.is_s3:
            base.errors.append(('Output directory must be on S3 '
                                'when running Rail-RNA in cloud ("--cloud") '
                                'mode, but {0} was entered.').format(
                                        base.output_dir
                                    ))
        if not base.force and ansible.s3_ansible.is_dir(base.output_dir):
            base.errors.append(('Output directory {0} exists on S3, and '
                                '"--force" was not invoked to permit '
                                'overwriting it.').format(base_output_dir))
        # Check manifest; download it if necessary
        manifest_url = ab.Url(base.manifest)
        if manifest_url.is_curlable \
            and 'Curl' not in base.checked_programs:
            base.curl_exe = base.check_program('curl', 'Curl', '--curl_exe',
                                    entered_exe=base.curl_exe,
                                    reason='the manifest file is on the web')
            ansible.curl_exe = base.curl_exe
        if not ansible.exists(manifest_url.to_url()):
            base.errors.append(('Manifest file ("--manifest") {0} '
                                'does not exist. Check the URL and '
                                'try again.').format(base.manifest))
        else:
            if not manifest_url.is_local:
                temp_manifest_dir = tempfile.mkdtemp()
                manifest = os.path.join(base.manifest_dir, 'MANIFEST')
                ansible.get(manifest_url, destination=temp_manifest)
            else:
                manifest = manifest_url.to_url()
            files_to_check = []
            with open(manifest) as manifest_stream:
                for line in manifest_stream:
                    tokens = line.strip().split('\t')
                    if len(tokens) == 5:
                        files_to_check.extend([tokens[0], tokens[2]])
                    elif len(tokens) == 3:
                        files_to_check.append(tokens[0])
                    else:
                        base.errors.append(('The following line from the '
                                            'manifest file {0} '
                                            'has an invalid number of '
                                            'tokens:\n{1}'
                                            ).format(
                                                    manifest_url.to_url(),
                                                    line
                                                ))
            if files_to_check:
                if check_manifest:
                    # Check files in manifest only if in preprocess job flow
                    for filename in files_to_check:
                        filename_url = ab.Url(filename)
                        if filename_url.is_curlable \
                            and 'Curl' not in base.checked_programs:
                            base.curl_exe = base.check_program('curl', 'Curl',
                                                '--curl_exe',
                                                entered_exe=base.curl_exe,
                                                reason=('at least one sample '
                                                  'FASTA/FASTQ from the '
                                                  'manifest file is on '
                                                  'the web'))
                            ansible.curl_exe = base.curl_exe
                        if not ansible.exists(filename_url):
                            base.errors.append(('The file {0} from the '
                                                'manifest file {1} does not '
                                                'exist the URL and try '
                                                'again.').format(
                                                        filename,
                                                        manifest_url.to_url()
                                                    ))
            else:
                base.errors.append(('Manifest file ("--manifest") {0} '
                                    'has no valid lines.').format(
                                                        manifest_url.to_url()
                                                    ))
            if not manifest_url.is_s3 and output_dir_url.is_s3:
                # Copy manifest file to S3 before job flow starts
                base.manifest = path_join(True, base.output_dir,
                                                manifest)
                ansible.put(manifest, base.manifest)
            if not manifest_url.is_local:
                # Clean up
                shutil.rmtree(temp_manifest_dir)

        actions_on_failure \
            = set(['TERMINATE_JOB_FLOW', 'CANCEL_AND_WAIT', 'CONTINUE',
                    'TERMINATE_CLUSTER'])

        if action_on_failure not in actions_on_failure:
            base.errors.append('Action on failure ("--action-on-failure") '
                               'must be one of {"TERMINATE_JOB_FLOW", '
                               '"CANCEL_AND_WAIT", "CONTINUE", '
                               '"TERMINATE_CLUSTER"}, but '
                               '{0} was entered.'.format(
                                                action_on_failure
                                            ))
        base.action_on_failure = action_on_failure
        base.hadoop_jar = hadoop_jar
        if not (isinstance(num_processes, int)
                and num_processes >= 1):
            base.errors.append('Number of processes ("--num-processes") must '
                               'be an integer >= 1, '
                               'but {0} was entered.'.format(
                                                num_processes
                                            ))
        base.tasks_per_reducer = tasks_per_reducer
        base.reducer_count = reducer_count
        instance_type_message = ('Instance type ("--instance-type") must be '
                                 'in the set {"m1.small", "m1.large", '
                                 '"m1.xlarge", "c1.medium", "c1.xlarge", '
                                 '"m2.xlarge", "m2.2xlarge", "m2.4xlarge", '
                                 '"cc1.4xlarge"}, but {0} was entered.')
        if master_instance_type not in base.instance_core_counts:
            base.errors.append(('Master instance type '
                               '("--master-instance-type") not valid. %s')
                                % instance_type_message.format(
                                                        master_instance_type
                                                    ))
        base.master_instance_type = master_instance_type
        if core_instance_type is None:
            base.core_instance_type = base.master_instance_type
        else:
            if core_instance_type not in base.instance_core_counts:
                base.errors.append(('Core instance type '
                                    '("--core-instance-type") not valid. %s')
                                    % instance_type_message.format(
                                                        core_instance_type
                                                    ))
            base.core_instance_type = core_instance_type
        if task_instance_type is None:
            base.task_instance_type = base.master_instance_type
        else:
            if task_instance_type not in base.instance_core_counts:
                base.errors.append(('Task instance type '
                                    '("--task-instance-type") not valid. %s')
                                    % instance_type_message.format(
                                                        task_instance_type
                                                    ))
            base.task_instance_type = task_instance_type
        if master_instance_bid_price is None:
            base.spot_master = False
        else:
            if not (isinstance(master_instance_bid_price, float) 
                    and master_instance_bid_price > 0):
                base.errors.append('Spot instance bid price for master nodes '
                                   '(--master-instance-bid-price) must be '
                                   '> 0, but {0} was entered.'.format(
                                                    master_instance_bid_price
                                                ))
            base.spot_master = True
            base.master_instance_bid_price = master_instance_bid_price
        if core_instance_bid_price is None:
            base.spot_core = False
        else:
            if not (isinstance(core_instance_bid_price, float) 
                    and core_instance_bid_price > 0):
                base.errors.append('Spot instance bid price for core nodes '
                                   '(--core-instance-bid-price) must be '
                                   '> 0, but {0} was entered.'.format(
                                                    core_instance_bid_price
                                                ))
            base.spot_core = True
            base.core_instance_bid_price = core_instance_bid_price
        if task_instance_bid_price is None:
            base.spot_task = False
        else:
            if not (isinstance(task_instance_bid_price, float) 
                    and task_instance_bid_price > 0):
                base.errors.append('Spot instance bid price for task nodes '
                                   '(--task-instance-bid-price) must be '
                                   '> 0, but {0} was entered.'.format(
                                                    task_instance_bid_price
                                                ))
            base.spot_task = True
            base.task_instance_bid_price = task_instance_bid_price
        if not (isinstance(master_instance_count, int)
                and master_instance_count >= 1):
            base.errors.append('Master instance count '
                               '("--master-instance-count") must be an '
                               'integer >= 1, but {0} was entered.'.format(
                                                    master_instance_count
                                                ))
        base.master_instance_count = master_instance_count
        if not (isinstance(core_instance_count, int)
                and core_instance_count >= 0):
            base.errors.append('Core instance count '
                               '("--core-instance-count") must be an '
                               'integer >= 1, but {0} was entered.'.format(
                                                    core_instance_count
                                                ))
        base.core_instance_count = core_instance_count
        if not (isinstance(task_instance_count, int)
                and task_instance_count >= 0):
            base.errors.append('Task instance count '
                               '("--task-instance-count") must be an '
                               'integer >= 1, but {0} was entered.'.format(
                                                    task_instance_count
                                                ))
        base.task_instance_count = task_instance_count
        if base.core_instance_count > 0:
            base.swap_allocation \
                = base.instance_swap_allocations[base.core_instance_type]
        else:
            base.swap_allocation \
                = base.instance_swap_allocations[base.master_instance_type]
        base.ec2_key_name = ec2_key_name
        base.keep_alive = keep_alive
        base.termination_protected = termination_protected

    @staticmethod
    def add_args(basic_group, advanced_group=None):
        basic_group.add_argument('--name', type=str, required=False,
            default='Rail-RNA Job Flow',
            help='Name of job flow on Elastic MapReduce'
        )
        basic_group.add_argument('--task-instance-count', type=str,
            required=False,
            default=0,
            help=('Number of task instances. A task instance runs Hadoop '
                  'maps and reduces and but does not store any data. This is '
                  'useful if running task instances as spot instances; if '
                  'the user loses spot instances because her bid price '
                  'fell below market value, her job flow will not fail.')
        )
        basic_group.add_argument('--core-instance-bid-price', type=str,
            required=False,
            default=None,
            help=('Bid price for core instances (in dollars/hour). Invoke '
                  'only if running core instances as spot instances.')
        )
        basic_group.add_argument('--task-instance-bid-price', type=str,
            required=False,
            default=None,
            help=('Bid price for each task instance (in dollars/hour). Invoke '
                  'only if running task instances as spot instances.')
        )
        basic_group.add_argument('--region', type=str,
            required=False,
            default='us-east-1',
            help='Amazon data center in which to run Elastic MapReduce job.'
        )
        if advanced_group is not None:
            advanced_group.add_argument('--log-uri', type=str, required=False,
                default=None,
                help=('Directory on S3 in which to store Hadoop logs. '
                      'Defaults to "logs" subdirectory of output directory.')
            )
            advanced_group.add_argument('--ami-version', type=str,
                required=False,
                default='2.4.2',
                help='Version of Amazon Linux AMI to use on EC2.'
            )
            advanced_group.add_argument('--visible-to-all-users',
                action='store_const',
                const=True,
                default=False,
                help='Makes EC2 cluster visible to all IAM users within the ' \
                     'EMR CLI'
            )
            advanced_group.add_argument('--action-on-failure', type=str,
                required=False,
                default='TERMINATE_JOB_FLOW',
                help='Specifies what action to take if a job flow fails on ' \
                     'a given step. Options are {"TERMINATE_JOB_FLOW", ' \
                     '"CANCEL_AND_WAIT", "CONTINUE", "TERMINATE_CLUSTER"}.'
            )
            advanced_group.add_argument('--hadoop-jar', type=str,
                required=False,
                default=('/home/hadoop/contrib/streaming/'
                         'hadoop-streaming-1.0.3.jar'),
                help='Hadoop Streaming Java ARchive to use. Controls ' \
                     'version of Hadoop Streaming.'
            )
            advanced_group.add_argument('--master-instance-count', type=str,
                required=False,
                default=1,
                usage=usage,
                help=('Number of master instances. A master instance helps '
                      'manage the cluster, tracking the status of each task.')
            )
            advanced_group.add_argument('-c', '--core-instance-count',
                type=str,
                required=False,
                default=1,
                usage=usage,
                help=('Number of core instances. A core instance runs Hadoop '
                      'maps and reduces and stores intermediate data.')
            )
            advanced_group.add_argument('--master-instance-bid-price',
                type=str,
                required=False,
                default=None,
                usage=usage,
                help=('Bid price for master instances (in dollars/hour). '
                      'Invoke only if running master instances as spot '
                      'instances.')
            )
            advanced_group.add_argument('--master-instance-type', type=str,
                required=False,
                default='c1.xlarge',
                usage=usage,
                help=('Master instance type. c1.xlarge is most cost-effective '
                      'across the board for Rail-RNA.')
            )
            advanced_group.add_argument('--core-instance-type', type=str,
                required=False,
                default=None,
                usage=usage,
                help=('Core instance type. c1.xlarge is most cost-effective '
                      'across the board for Rail-RNA. Defaults to master '
                      'instance type if left unspecified.')
            )
            advanced_group.add_argument('--task-instance-type', type=str,
                required=False,
                default=None,
                help=('Task instance type. c1.xlarge is most cost-effective '
                      'across the board for Rail-RNA. Defaults to master '
                      'instance type if left unspecified.')
            )
            advanced_group.add_argument('--ec2-key-name', type=str,
                reqired=False,
                default=None,
                help=('Name of key pair for connecting to EC2 instances via, '
                      'for example, SSH. May be useful for debugging.')
            )
            advanced_group.add_argument('--keep-alive', type=str,
                required=False,
                default=False,
                help='Keeps EC2 cluster alive after job flow is completed.'
            )
            advanced_group.add_argument('--termination-protected', type=str,
                required=False,
                default=False,
                help='Protects cluster from termination in case of job flow ' \
                     'failure.'
            )

    @staticmethod
    def hadoop_debugging_steps(base):
        return [
            {
                'ActionOnFailure' : base.action_on_failure,
                'HadoopJarStep' : {
                    'Args' : [
                        ('s3://us-east-1.elasticmapreduce/libs/'
                         'state-pusher/0.1/fetch')
                    ],
                    'Jar' : ('s3://us-east-1.elasticmapreduce/libs/'
                             'script-runner/script-runner.jar')
                },
                'Name' : 'Set up Hadoop Debugging'
            }
        ]

    @staticmethod
    def bootstrap(base):
        return [
            {
                'Name' : 'Allocate swap space',
                'ScriptBootstrapAction' : {
                    'Args' : [
                        base.swap_allocation
                    ],
                    'Path' : 's3://elasticmapreduce/bootstrap-actions/add-swap'
                }
            },
            {
                'Name' : 'Configure Hadoop',
                'ScriptBootstrapAction' : {
                    'Args' : [
                        '-s',
                        'mapred.job.reuse.jvm.num.tasks=1',
                        '-s',
                        'mapred.tasktracker.reduce.tasks.maximum=8',
                        '-s',
                        'mapred.tasktracker.map.tasks.maximum=8',
                        '-m',
                        'mapred.map.tasks.speculative.execution=false',
                        '-m',
                        'mapred.reduce.tasks.speculative.execution=false'
                    ],
                    'Path' : ('s3://elasticmapreduce/bootstrap-actions/'
                              'configure-hadoop')
                }
            }
        ]

    @staticmethod
    def instances(base):
        to_return = {
            'HadoopVersion' : '1.0.3',
            'InstanceGroups' : [
                {
                    'InstanceCount' : base.master_instance_count,
                    'InstanceRole' : 'MASTER',
                    'InstanceType': base.master_instance_type,
                    'Name' : 'Master Instance Group'
                },
                {
                    'InstanceCount' : base.core_instance_count,
                    'InstanceRole' : 'CORE',
                    'InstanceType': base.core_instance_type,
                    'Name' : 'Core Instance Group'
                },
                {
                    'InstanceCount' : base.task_instance_count,
                    'InstanceRole' : 'MASTER',
                    'InstanceType': base.task_instance_type,
                    'Name' : 'Task Instance Group'
                }
            ],
            'KeepJobFlowAliveWhenNoSteps': 'false',
            'TerminationProtected': ('true' if base.termination_protected
                                        else 'false')
        }
        if base.ec2_key_name is not None:
            to_return['Ec2KeyName'] = base.ec2_key_name
        if base.master_instance_bid_price is not None:
            to_return['InstanceGroups'][0]['BidPrice'] \
                = '%0.03f' % base.master_instance_bid_price
            to_return['InstanceGroups'][0]['Market'] \
                = 'SPOT'
        else:
            to_return['InstanceGroups'][0]['Market'] \
                = 'ON_DEMAND'
        if base.core_instance_bid_price is not None:
            to_return['InstanceGroups'][1]['BidPrice'] \
                = '%0.03f' % base.core_instance_bid_price
            to_return['InstanceGroups'][1]['Market'] \
                = 'SPOT'
        else:
            to_return['InstanceGroups'][1]['Market'] \
                = 'ON_DEMAND'
        if base.task_instance_bid_price is not None:
            to_return['InstanceGroups'][2]['BidPrice'] \
                = '%0.03f' % base.task_instance_bid_price
            to_return['InstanceGroups'][2]['Market'] \
                = 'SPOT'
        else:
            to_return['InstanceGroups'][2]['Market'] \
                = 'ON_DEMAND'
        return to_return

class RailRnaPreprocess:
    """ Sets parameters relevant to just the preprocessing step of a job flow.
    """
    def __init__(self, base, nucleotides_per_input=8000000, gzip_input=True):
        if not (isinstance(nucleotides_per_input, int) and
                nucleotides_per_input > 0):
            base.errors.append('Nucleotides per input '
                               '(--nucleotides-per-input) must be an integer '
                               '> 0, but {0} was entered.'.format(
                                                        nucleotides_per_input
                                                       ))
        base.nucleotides_per_input = nucleotides_per_input
        base.gzip_input = gzip_input

    @staticmethod
    def add_args(parser):
        """ Adds parameter descriptions relevant to preprocess job flow to an
            object of class argparse.ArgumentParser.

            No return value.
        """
        parser.add_argument(
            '--nucleotides-per-input', type=int, required=False,
            default=8000000,
            help=('Maximum number of nucleotides from a given sample to '
                  'assign to each task. Keep this value small enough that '
                  'there are at least as many tasks as there are processor '
                  'cores available.')
        )
        parser.add_argument(
            '--do-not-gzip-output', action='store_const', const=True,
            default=False,
            help=('Leaves output of preprocess step uncompressed. This makes '
                  'preprocessing faster but takes up more hard drive space.')
        )

    @staticmethod
    def protosteps(base, output_dir):
        return [
            {
                'name' : 'Preprocess input reads',
                'run' : ('preprocess.py --nucs-per-file={0} {1} '
                         '--push={2} --ignore-first-token').format(
                                                    base.nucleotides_per_file,
                                                    '--gzip-output' if
                                                    base.gzip_output else '',
                                                    output_dir
                                                ),
                'inputs' : [base.manifest],
                'output' : output_dir,
                'no_output_prefix' : True,
                'inputformat' : (
                        'org.apache.hadoop.mapred.lib.NLineInputFormat'
                    ),
                'taskx' : 0
            }
        ]

    @staticmethod
    def bootstrap():
        return [
            {
                'Name' : 'PyPy',
                'ScriptBootstrapAction' : {
                    'Args' : [
                        ('s3://rail-emr/bin/'
                         'pypy-2.2.1-linux_x86_64-portable.tar.bz2')
                    ],  
                    'Path' : 's3://rail-emr/bootstrap/install-pypy.sh'
                }
            }
        ]

class RailRnaAlign:
    """ Sets parameters relevant to just the "align" job flow. """
    def __init__(self, base, input_dir=None, cloud=False,
        bowtie1_exe=None, bowtie1_idx='genome', bowtie1_build_exe=None,
        bowtie2_exe=None, bowtie2_build_exe=None, bowtie2_idx='genome',
        bowtie2_args='', samtools_exe=None, bedtobigbed_exe=None,
        genome_partition_length=5000, max_readlet_size=25,
        min_readlet_size=15, readlet_interval=4, cap_size_multiplier=1.2,
        max_intron_size=500000, min_intron_size=10, min_exon_size=9,
        motif_search_window_size=1000, motif_radius=5,
        normalize_percentile=0.75, do_not_output_bam_by_chr=False,
        output_sam=False, bam_basename='alignments', bed_basename='',
        assembly='hg19', s3_ansible=None):
        if not cloud:
            '''Programs and Bowtie indices should be checked only in local
            mode.'''
            base.bowtie1_exe = base.check_program('bowtie', 'Bowtie 1',
                                '--bowtie1-exe', entered_exe=bowtie1_exe)
            base.bowtie1_build_exe = base.check_program('bowtie-build',
                                            'Bowtie 1 Build',
                                            '--bowtie1-build-exe',
                                            entered_exe=bowtie1_build_exe)
            for extension in ['.1.ebwt', '.2.ebwt', '.3.ebwt', '.4.ebwt', 
                                '.rev.1.ebwt', '.rev.2.ebwt']:
                index_file = bowtie1_idx + extension
                if not ab.Url(index_file).is_local:
                    base_errors.append(('Bowtie 1 index file {0} must be '
                                        'on the local filesystem.').format(
                                            index_file
                                        ))
                elif not os.path.exists(index_file):
                    base.errors.append(('Bowtie 1 index file {0} does not '
                                        'exist.').format(index_file))
            base.bowtie1_idx = bowtie1_idx
            base.bowtie2_exe = base.check_program('bowtie2', 'Bowtie 2',
                                '--bowtie2-exe', entered_exe=bowtie2_exe)
            base.bowtie2_build_exe = base.check_program('bowtie-build',
                                            'Bowtie 2 Build',
                                            '--bowtie2-build-exe',
                                            entered_exe=bowtie2_build_exe)
            for extension in ['.1.bt2', '.2.bt2', '.3.bt2', '.4.bt2', 
                                '.rev.1.bt2', '.rev.2.bt2']:
                index_file = bowtie2_idx + extension
                if not ab.Url(index_file).is_local:
                    base_errors.append(('Bowtie 2 index file {0} must be '
                                        'on the local filesystem.').format(
                                            index_file
                                        ))
                elif not os.path.exists(index_file):
                    base.errors.append(('Bowtie 2 index file {0} does not '
                                        'exist.').format(index_file))
            base.bowtie2_idx = bowtie2_idx
            base.samtools_exe = base.check_program('samtools', 'SAMTools',
                                '--samtools-exe', entered_exe=samtools_exe)
            base.bedtobigbed_exe = base.check_program('bedToBigBed', 
                                    'BedToBigBed', '--bedtobigbed-exe',
                                    entered_exe=bedtobigbed_exe)
            # Check input dir
            if input_dir is not None:
                if not os.path.exists(input_dir):
                    base_errors.append(('Input directory ("--input-dir") '
                                        '"{0}" does not exist').format(
                                                            input_dir
                                                        ))
                else:
                    base.input_dir = input_dir
        else:
            # Cloud mode; check S3 for genome if necessary
            assert s3_ansible is not None
            if assembly == 'hg19':
                base.index_archive = 's3://rail-emr/index/hg19_UCSC.tar.gz'
            else:
                if not Url(assembly).is_s3:
                    base.errors.append(('Bowtie index archive must be on S3'
                                        ' in cloud ("--cloud") mode, but '
                                        '"{0}" was entered.').format(assembly))
                elif not s3_ansible.exists(assembly):
                    base.errors.append('Bowtie index archive was not found '
                                       'on S3 at "{0}".'.format(assembly))
                else:
                    base.index_archive = assembly
            if input_dir is not None:
                if not Url(input_dir).is_s3:
                    base.errors.append(('Input directory must be on S3, but '
                                        '"{0}" was entered.').format(
                                                                input_dir
                                                            ))
                elif not s3_ansible.is_dir(input_dir):
                    base.errors.append(('Input directory "{0}" was not found '
                                        'on S3.').format(input_dir))
                else:
                    base.input_dir = input_dir
            # Set up cloud params
            base.bowtie1_idx = '/mnt/index/genome'
            base.bowtie2_idx = '/mnt/index/genome'
            base.bedtobigbed_exe='/mnt/bin/bedToBigBed'
            base.samtools_exe='samtools'
            base.bowtie1_exe='bowtie'
            base.bowtie2_exe='bowtie2'
            base.bowtie1_build_exe='bowtie-build'
            base.bowtie2_build_exe='bowtie2-build'

        # Assume bowtie2 args are kosher for now
        base.bowtie2_args = bowtie2_args
        if not (isinstance(genome_partition_length, int) and
                genome_partition_length > 0):
            base.errors.append('Genome partition length '
                               '(--genome-partition-length) must be an '
                               'integer > 0, but {0} was entered.'.format(
                                                        genome_partition_length
                                                    ))
        base.genome_partition_length = genome_partition_length
        if not (isinstance(min_readlet_size, int) and min_readlet_size > 0):
            base.errors.append('Minimum readlet size (--min-readlet-size) '
                               'must be an integer > 0, but '
                               '{0} was entered.'.format(min_readlet_size))
        base.min_readlet_size = min_readlet_size
        if not (isinstance(max_readlet_size, int) and max_readlet_size
                >= min_readlet_size):
            base.errors.append('Maximum readlet size (--max-readlet-size) '
                               'must be an integer >= minimum readlet size '
                               '(--min-readlet-size) = '
                               '{0}, but {1} was entered.'.format(
                                                    base.min_readlet_size,
                                                    max_readlet_size
                                                ))
        base.max_readlet_size = max_readlet_size
        if not (isinstance(readlet_interval, int) and readlet_interval
                > 0):
            base.errors.append('Readlet interval (--readlet-interval) '
                               'must be an integer > 0, '
                               'but {0} was entered.'.format(
                                                    readlet_interval
                                                ))
        base.readlet_interval = readlet_interval
        if not (isinstance(cap_size_multiplier, float) and cap_size_multiplier
                > 1):
            base.errors.append('Cap size multiplier (--cap-size-multiplier) '
                               'must be > 1, '
                               'but {0} was entered.'.format(
                                                    cap_size_multiplier
                                                ))
        base.cap_size_multiplier = cap_size_multiplier
        if not (isinstance(min_intron_size, int) and min_intron_size > 0):
            base.errors.append('Minimum intron size (--min-intron-size) '
                               'must be an integer > 0, but '
                               '{0} was entered.'.format(min_intron_size))
        base.min_intron_size = min_intron_size
        if not (isinstance(max_intron_size, int) and max_intron_size
                >= min_intron_size):
            base.errors.append('Maximum intron size (--max-intron-size) '
                               'must be an integer >= minimum intron size '
                               '(--min-readlet-size) = '
                               '{0}, but {1} was entered.'.format(
                                                    base.min_intron_size,
                                                    max_intron_size
                                                ))
        base.max_intron_size = max_intron_size
        if not (isinstance(min_exon_size, int) and min_exon_size > 0):
            base.errors.append('Minimum exon size (--min-exon-size) '
                               'must be an integer > 0, but '
                               '{0} was entered.'.format(min_exon_size))
        base.min_exon_size = min_exon_size
        if not (isinstance(motif_search_window_size, int) and 
                    motif_search_window_size >= 0):
            base.errors.append('Motif search window size '
                               '(--motif-search-window-size) must be an '
                               'integer > 0, but {0} was entered.'.format(
                                                    motif_search_window_size
                                                ))
        if not (isinstance(motif_radius, int) and
                    motif_radius >= 0):
            base.errors.append('Motif radius (--motif-radius) must be an '
                               'integer >= 0, but {0} was entered.'.format(
                                                    motif_radius
                                                ))
        base.motif_radius = motif_radius
        if not (isinstance(normalize_percentile, float) and
                    0 <= normalize_percentile <= 1):
            base.errors.append('Normalization percentile '
                               '(--normalize-percentile) must on the '
                               'interval [0, 1], but {0} was entered'.format(
                                                    normalize_percentile
                                                ))
        base.normalize_percentile = normalize_percentile
        base.do_not_output_bam_by_chr = do_not_output_bam_by_chr
        base.output_sam = output_sam
        base.bam_basename = bam_basename
        base.bed_basename = bed_basename

    @staticmethod
    def add_args(basic_group, advanced_group=None, cloud=False):
        """ usage: argparse.SUPPRESS if advanced options should be suppressed;
                else None
        """
        if not cloud:
            basic_group.add_argument(
                '--bowtie1-exe', type=str, required=False,
                default=None,
                help=('Path to Bowtie 1 executable. This can be left out if '
                      '"bowtie" is in PATH and is executable.')
            )
            basic_group.add_argument(
                '-1', '--bowtie1-idx', type=str, required=True,
                help='Path to Bowtie 1 index. Include basename.'
            )
            basic_group.add_argument(
                '--bowtie2-exe', type=str, required=False,
                default=None,
                help=('Path to Bowtie 2 executable. This can be left out if '
                      '"bowtie2" is in PATH and is executable.')
            )
            basic_group.add_argument(
                '-2', '--bowtie2-idx', type=str, required=True,
                help='Path to Bowtie 2 index. Include basename.'
            )
            basic_group.add_argument(
                '--bowtie2_args', type=str, required=False,
                default='',
                help=('Additional arguments to pass to Bowtie 2, which is '
                      'used to obtain final end-to-end alignments and spliced '
                      'alignments in output SAM/BAM files.')
            )
            basic_group.add_argument(
                '--samtools-exe', type=str, required=False,
                default=None,
                help=('Path to SAMTools executable. This can be left out if '
                      '"samtools" is in PATH and is executable.')
            )
            basic_group.add_argument(
                '--bedtobigbed-exe', type=str, required=False,
                default=None,
                help=('Path to BedToBigBed executable. This can be left out '
                      'if "bedToBigBed" is in PATH and is executable.')
            )
        else:
            basic_group.add_argument(
                '--assembly', type=str, required=False,
                default='hg19',
                help=('One of the following:\n'
                      '   a) An assembly identifier for a supported '
                      'organism. Currently supported: {"hg19"}.\n'
                      '   b) Accessible S3 path to a Rail archive. A Rail '
                      'archive is a tar.gz composed a folder titled "index", '
                      'that contains BOTH Bowtie 1 and Bowtie 2 index files '
                      '(12 in total), all with the basename "genome".')
            )
        basic_group.add_argument(
            '--max-intron-size', type=int, required=False,
            default=500000,
            help=('Introns spanning more than this many nucleotides are '
                  'automatically filtered out.')
        )
        basic_group.add_argument(
            '--min-intron-size', type=int, required=False,
            default=10,
            help=('Introns spanning fewer than this many nucleotides are '
                  'automatically filtered out.')
        )
        basic_group.add_argument(
            '--min-exon-size', type=int, required=False,
            default=9,
            help=('The aligner will not be sensitive to exons smaller than '
                  'this size.')
        )
        basic_group.add_argument(
            '--normalize-percentile', type=float, required=False,
            default=0.75,
            help=('Percentile used for computing normalization factors for '
                  'sample coverage.')
        )
        basic_group.add_argument(
            '--do-not-output-bam-by-chr', action='store_const', const=True,
            default=False,
            help=('Places alignments for all chromosomes in a single file '
                  'rather than dividing them up by reference name.')
        )
        basic_group.add_argument(
            '--output-sam', action='store_const', const=True,
            default=False,
            help='Outputs SAM files rather than BAM files.'
        )
        basic_group.add_argument(
            '--bam-basename', type=str, required=False,
            default='alignments',
            help='Basename to use for BAM output files.'
        )
        basic_group.add_argument(
            '--bed-basename', type=str, required=False,
            default='',
            help=('Basename to use for BED output files; there is an output '
                  'for each of insertions, deletions, and introns.')
        )
        if advanced_group is not None:
            advanced_group.add_argument(
                '--genome-partition-length', type=int, required=False,
                default=5000,
                help=('Smallest unit of a genome (in nucleotides) addressable '
                      'by a single task when computing coverage from exon '
                      'differentials. Making this parameter too small '
                      '(~hundreds of nucleotides) can bloat intermediate '
                      'files, but making it too large '
                      '(~the size of a chromosome) could compromise '
                      'the scalability of the pipeline.')
            )
            advanced_group.add_argument(
                '--max-readlet-size', type=int, required=False,
                default=25,
                help=('Maximum size of a given segment from a read that is 1) '
                      'mapped to the genome using Bowtie 1 when searching for '
                      'introns; and 2) mapped to a set of transcriptome '
                      'elements using Bowtie 2 when finalizing spliced '
                      'alignments. Decreasing the value of this parameter '
                      'may increase recall of introns while compromising '
                      'precision. For human-size genomes, values between '
                      '20 and 25 are recommended.')
            )
            advanced_group.add_argument(
                '--min-readlet-size', type=int, required=False,
                default=15,
                help=('Minimum size of a given "capping readlet" -- that is, '
                      'a read segment whose end coincides with a read end '
                      '-- that is a) mapped to the genome using Bowtie 1 '
                      'when searching for introns; and 2) mapped to a set of '
                      'transcriptome elements using Bowtie 2 when finalizing '
                      'spliced alignments. Decreasing the value of this '
                      'parameter may increase recall of rare introns '
                      'overlapped towards the ends of a few reads in a sample '
                      'while compromising precision.')
            )
            advanced_group.add_argument(
                '--readlet-interval', type=int, required=False,
                default=4,
                help=('Distance (in nucleotides) between overlapping readlets '
                      'mapped to genome and set of transcriptome elements. '
                      'Decreasing this parameter may increase sensitivity '
                      'while increasing the time the pipeline takes.')
            )
            advanced_group.add_argument(
                '--cap-size-multiplier', type=float, required=False,
                default=1.2,
                help=('Successive capping readlets on a given end of a read '
                      'are increased in size exponentially with this base.')
            )
            advanced_group.add_argument(
                '--motif-search-window-size', type=int, required=False,
                default=1000,
                help=('Size of window in which to search for exons of size '
                      '"--min-exon-size" capped by appropriate donor/acceptor '
                      'motifs when inferring intron positions.')
            )
            advanced_group.add_argument(
                '--motif-radius', type=int, required=False,
                default=5,
                help=('Number of nucleotides of ostensible intron ends within '
                      'which to search for a donor/acceptor motif.')
            )

    @staticmethod
    def protosteps(base, input_dir, cloud=False):
        manifest = ('/mnt/MANIFEST' if cloud else base.manifest)
        verbose = ('--verbose' if base.verbose else '')
        keep_alive = ('--keep-alive' if cloud else '')
        return [  
            {
                'name' : 'Align reads to genome',
                'run' : ('align.py --bowtie-idx={0} --bowtie2_idx={1}'
                         '--bowtie2-exe={2}'
                         '--exon-differentials --partition-length={3}'
                         '--manifest={4} {5}').format(base.bowtie1_idx,
                                                        base.bowtie2_idx,
                                                        base.bowtie2_exe,
                                                        base.partition_length,
                                                        manifest,
                                                        verbose),
                'inputs' : [input_dir],
                'no_input_prefix' : True,
                'output' : 'align_reads',
                'taskx' : 0,
                'multiple_outputs' : True
            },
            {
                'name' : 'Aggregate duplicate read sequences',
                'run' : 'sum.py --type 3 --value-count 2',
                'inputs' : [path_join(cloud, 'align_reads', 'readletize')],
                'output' : 'combine_sequences',
                'taskx' : 4,
                'part' : 'k1,1',
                'keys' : 1
            },
            {
                'name' : 'Segment reads into readlets',
                'run' : ('readletize.py --max_readlet_size={0} '
                         '--readlet-interval={1} '
                         '--capping-multiplier={2}').format(
                                    base.max_readlet_size,
                                    base.readlet_interval,
                                    base.cap_size_multiplier
                                ),
                'inputs' : [path_join(cloud, 'align_reads', 'readletize')],
                'output' : 'combine_sequences',
                'taskx' : 4,
                'part' : 'k1,1',
                'keys' : 1
            },
            {
                'name' : 'Aggregate duplicate readlet sequences',
                'run' : 'sum.py --type 3',
                'inputs' : ['readletize'],
                'output' : 'combine_subsequences',
                'taskx' : 4,
                'part' : 'k1,1',
                'keys' : 1
            },
            {
                'name' : 'Align unique readlets to genome',
                'run' : ('align_readlets.py --bowtie-idx={0} '
                         '--bowtie-exe={1} {2}'
                         '-- -t --sam-nohead --startverbose '
                         '-v 0 -a -m 80').format(
                                    base.bowtie_idx,
                                    base.bowtie_exe,
                                    verbose
                                ),
                'inputs' : [path_join(cloud, 'align_reads', 'readletize')],
                'output' : 'combine_sequences',
                'taskx' : 4,
                'part' : 'k1,1',
                'keys' : 1
            },
            {
                'name' : 'Search for introns using readlet alignments',
                'run' : ('intron_search.py --bowtie-idx={0} '
                         '--partition-length={1} --max-intron-size={2}'
                         '--min-intron-size={3} --min-exon-size={4}'
                         '--search-window-size={5} '
                         '--motif-radius={6} {7}').format(base.bowtie1_idx,
                                                        base.partition_length,
                                                        base.max_intron_size,
                                                        base.min_intron_size,
                                                        base.min_exon_size,
                                                base.motif_search_window_size,
                                                        base.motif_radius,
                                                        verbose),
                'inputs' : ['align_readlets'],
                'output' : 'intron_search',
                'taskx' : 4,
                'part' : 'k1,1',
                'keys' : 1
            },
            {
                'name' : 'Enumerate possible intron cooccurrences on readlets',
                'run' : ('intron_config.py '
                         '--readlet-size={0} {1}').format(
                                                        base.max_readlet_size,
                                                        verbose
                                                    ),
                'inputs' : ['intron_search'],
                'output' : 'intron_config',
                'taskx' : 1,
                'part' : 'k1,2',
                'keys' : 4
            },
            {
                'name' : 'Get transcriptome elements for readlet realignment',
                'run' : ('intron_fasta.py --bowtie-idx={0} {1}').format(
                                                        base.bowtie1_idx,
                                                        verbose
                                                    ),
                'inputs' : ['intron_config'],
                'output' : 'intron_fasta',
                'taskx' : 8,
                'part' : 'k1,4',
                'keys' : 4
            },
            {
                'name' : 'Build index of transcriptome elements',
                'run' : ('intron_index.py --bowtie-build-exe={0}'
                         '--out={1} {2}').format(base.bowtie1_build_exe,
                                                 path_join(cloud,
                                                            base.utput_dir,
                                                            index),
                                                 keep_alive),
                'inputs' : ['intron_fasta'],
                'output' : 'intron_index',
                'taskx' : None,
                'part' : 'k1,1',
                'keys' : 1
            },
            {
                'name' : 'Align readlets to transcriptome elements',
                'run' : ('align_readlets.py --bowtie-idx={0} '
                         '--bowtie-exe={1} {2} -- -t --sam-nohead '
                         '--startverbose -v -a -m 80').format(
                                                        'intron/intron'
                                                        if cloud else
                                                        path_join(cloud,
                                                            base.output_dir,
                                                            index,
                                                            intron),
                                                        base.bowtie1_exe,
                                                        verbose
                                                    ),
                'inputs' : ['combine_subsequences'],
                'output' : 'realign_readlets',
                'taskx' : 4,
                'archives' : ('s3n://rail-experiments/geuvadis_again/index/'
                              'intron.tar.gz#intron'),
                'part' : 'k1,1',
                'keys' : 1,
            },
            {
                'name' : 'Finalize intron cooccurrences on reads',
                'run' : ('cointron_search.py {0}').format(verbose),
                'inputs' : ['realign_readlets', 'align_readlets'],
                'output' : 'cointron_search',
                'taskx' : 4,
                'part' : 'k1,1',
                'keys' : 1
            },
            {
                'name' : 'Align reads to transcriptome elements',
                'run' : ('realign_reads.py --original-idx={0} '
                         '--bowtie2-exe={1} --partition-length={2} '
                         '--exon-differentials --manifest={3} {4} '
                         '-- --end-to-end').format(base.bowtie1_idx,
                                                    base.bowtie2_exe,
                                                    base.partition_length,
                                                    manifest,
                                                    verbose),
                'inputs' : ['cointron_fasta'],
                'output' : 'realign_reads',
                'taskx' : 4,
                'part' : 'k1,1',
                'keys' : 1,
                'multiple_outputs' : True
            },
            {
                'name' : 'Merge exon differentials at same genomic positions',
                'run' : 'sum.py',
                'inputs' : [path_join(cloud, 'align_reads', 'exon_diff'),
                            path_join(cloud, 'realign_reads', 'exon_diff')],
                'output' : 'collapse',
                'taskx' : 8,
                'part' : 'k1,3',
                'keys' : 3
            },
            {
                'name' : 'Compile sample coverages from exon differentials',
                'run' : ('coverage_pre.py --bowtie-idx={0} '
                         '--partition-stats').format(base.bowtie1_idx),
                'inputs' : ['collapse'],
                'output' : 'coverage_pre',
                'taskx' : 8,
                'part' : 'k1,2',
                'keys' : 3,
                'multiple_outputs' : True
            },
            {
                'name' : 'Write bigbeds with exome coverage by sample',
                'run' : ('coverage.py --bowtie-idx={0} --percentile={1}'
                         '--out={2} --bigbed-exe={3} '
                         '--manifest={4} {5}').format(base.bowtie_idx,
                                                     base.normalize_percentile,
                                                     path_join(cloud,
                                                        base.output_dir,
                                                        'coverage'),
                                                     base.bigbed_exe,
                                                     manifest,
                                                     verbose),
                'inputs' : [path_join(cloud, 'coverage_pre', 'coverage')],
                'output' : 'coverage',
                'taskx' : 1,
                'part' : 'k1,1',
                'keys' : 3
            },
            {
                'name' : 'Write normalization factors for sample coverages',
                'run' : 'coverage_post --out={0} --manifest={1}'.format(
                                                        path_join(cloud,
                                                            base.output_dir,
                                                            'normalize'),
                                                        manifest
                                                    ),
                'inputs' : ['coverage'],
                'output' : 'coverage_post',
                'taskx' : None,
                'part' : 'k1,1',
                'keys' : 2
            },
            {
                'name' : 'Aggregate intron and index results by sample',
                'run' : 'bed_pre.py',
                'inputs' : [path_join(cloud, 'realign_reads', 'bed'),
                            path_join(cloud, 'align_reads', 'bed')],
                'output' : 'bed_pre',
                'taskx' : 8,
                'part' : 'k1,6',
                'keys' : 6
            },
            {
                'name' : 'Write beds with intron and indel results by sample',
                'run' : ('bed.py --bowtie-idx={0} --out={1} '
                         '--manifest={2} --bed-basename={3}').format(
                                                        base.bowtie1_idx,
                                                        path_join(cloud,
                                                            output_dir,
                                                            'bed'),
                                                        manifest,
                                                        base.bed_basename
                                                    ),
                'inputs' : ['bed_pre'],
                'output' : 'bed',
                'taskx' : 1,
                'part' : 'k1,2',
                'keys' : 4,
            },
            {
                'name' : 'Write bams with alignments by sample',
                'run' : ('bam.py --out={0} --bowtie-idx={1} '
                         '--samtools-exe={2} --bam-basename={3} '
                         '--manifest={4} {5}').format(
                                        path_join(cloud, output_dir, 'bam'),
                                        base.bowtie1_idx,
                                        base.samtools_exe,
                                        base.bam_basename,
                                        manifest,
                                        keep_alive
                                    ),
                'inputs' : [path_join(cloud, 'align_reads', 'end_to_end_sam'),
                            path_join(cloud, 'realign_reads', 'splice_sam')],
                'output' : 'bam',
                'taskx' : 1,
                'part' : 'k1,1',
                'keys' : 3
            }]

    @staticmethod
    def bootstrap(base):
        return [
            {
                'Name' : 'Install PyPy',
                'ScriptBootstrapAction' : {
                    'Args' : [
                        ('s3://rail-emr/bin/'
                         'pypy-2.2.1-linux_x86_64-portable.tar.bz2')
                    ],
                    'Path' : 's3://rail-emr/bootstrap/install-pypy.sh'
                }
            },
            {
                'Name' : 'Install Bowtie 1',
                'ScriptBootstrapAction' : {
                    'Args' : [],
                    'Path' : 's3://rail-emr/bootstrap/install-bowtie.sh'
                }
            },
            {
                'Name' : 'Install Bowtie 2',
                'ScriptBootstrapAction' : {
                    'Args' : [],
                    'Path' : 's3://rail-emr/bootstrap/install-bowtie2.sh'
                }
            },
            {
                'Name' : 'Install BedToBigBed',
                'ScriptBootstrapAction' : {
                    'Args' : [
                        '/mnt/bin'
                    ],
                    'Path' : 's3://rail-emr/bootstrap/install-kenttools.sh'
                }
            },
            {
                'Name' : 'Install SAMTools',
                'ScriptBootstrapAction' : {
                    'Args' : [],
                    'Path' : 's3://rail-emr/bootstrap/install-samtools.sh'
                }
            },
            {
                'Name' : 'Install Rail-RNA',
                'ScriptBootstrapAction' : {
                    'Args' : [
                        's3://rail-emr/bin/rail-rna-0.1.0.tar.gz',
                        '/mnt'
                    ],
                    'Path' : 's3://rail-emr/bootstrap/install-rail.sh'
                }
            },
            {
                'Name' : 'Transfer Bowtie indexes to nodes',
                'ScriptBootstrapAction' : {
                    'Args' : [
                        '/mnt',
                        base.assembly
                    ],
                    'Path' : 's3://rail-emr/bootstrap/s3cmd_s3_tarball.sh'
                }
            },
            {
                'Name' : 'Transfer manifest file to nodes',
                'ScriptBootstrapAction' : {
                    'Args' : [
                        base.manifest,
                        '/mnt',
                        'MANIFEST'
                    ],
                    'Path' : 's3://rail-emr/bootstrap/s3cmd_s3.sh'
                }
            }
        ]

class RailRnaLocalPreprocessJson:
    """ Constructs JSON for local mode + preprocess job flow. """
    def __init__(self, manifest, output_dir, intermediate_dir='./intermediate',
        force=False, aws_exe=None, profile='default', region='us-east-1',
        verbose=False, nucleotides_per_input=8000000, gzip_input=True,
        num_processes=1, keep_intermediates=False):
        base = RailRnaErrors(manifest, output_dir, 
            intermediate_dir=intermediate_dir,
            force=force, aws_exe=aws_exe, profile=profile,
            region=region, verbose=verbose)
        RailRnaLocal(base, check_manifest=True, num_processes=num_processes,
            keep_intermediates=keep_intermediates)
        RailRnaPreprocess(base, nucleotides_per_input=nucleotides_per_input,
            gzip_input=gzip_input)
        if base.errors:
            raise RuntimeError(
                    '\n'.join(
                            ['%d) %s' % (i, error) for i, error in errors]
                        )
                )
        self._json_serial = {}
        step_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 
                                                    'steps'))
        self._json_serial['Steps'] = steps(RailRnaPreprocess.protosteps(base,
                base.output_dir), '', '', step_dir, base.num_processes,
                base.intermediate_dir, unix=False
            )
    
    @property
    def json_serial(self):
        return self._json_serial

class RailRnaCloudPreprocessJson:
    """ Constructs JSON for cloud mode + preprocess job flow. """
    def __init__(self, manifest, output_dir, intermediate_dir='./intermediate',
        force=False, aws_exe=None, profile='default', region='us-east-1',
        verbose=False, nucleotides_per_input=8000000, gzip_input=True,
        log_uri=None, ami_version='2.4.2',
        visible_to_all_users=False, tags='',
        name='Rail-RNA Job Flow',
        action_on_failure='TERMINATE_JOB_FLOW',
        hadoop_jar='/home/hadoop/contrib/streaming/hadoop-streaming-1.0.3.jar',
        master_instance_count=1, master_instance_type='c1.xlarge',
        master_instance_bid_price=None, core_instance_count=1,
        core_instance_type=None, core_instance_bid_price=None,
        task_instance_count=0, task_instance_type=None,
        task_instance_bid_price=None, ec2_key_name=None, keep_alive=False,
        termination_protected=False):
        base = RailRnaErrors(manifest, output_dir, 
            intermediate_dir=intermediate_dir,
            force=force, aws_exe=aws_exe, profile=profile,
            region=region, verbose=verbose)
        RailRnaCloud(base, check_manifest=True,
            log_uri=log_uri, ami_version=ami_version,
            visible_to_all_users=visible_to_all_users, tags=tags,
            name=name,
            action_on_failure=action_on_failure,
            hadoop_jar=hadoop_jar, master_instance_count=master_instance_count,
            master_instance_type=master_instance_type,
            master_instance_bid_price=master_instance_bid_price,
            core_instance_count=core_instance_count,
            core_instance_type=core_instance_type,
            core_instance_bid_price=core_instance_bid_price,
            task_instance_count=task_instance_count,
            task_instance_type=task_instance_type,
            task_instance_bid_price=task_instance_bid_price,
            ec2_key_name=ec2_key_name, keep_alive=keep_alive,
            termination_protected=termination_protected)
        RailRnaPreprocess(base, nucleotides_per_input=nucleotides_per_input,
            gzip_input=gzip_input)
        if base.errors:
            raise RuntimeError(
                    '\n'.join(
                            ['%d) %s' % (i, error) for i, error in errors]
                        )
                )
        self._json_serial = {}
        if base.core_instance_count > 0:
            reducer_count = base.core_instance_count \
                * base.instance_core_counts[base.core_instance_type]
        else:
            reducer_count = base.master_instance_count \
                * base.instance_core_counts[base.core_instance_type]
        self._json_serial['Steps'] \
            = RailRnaCloud.hadoop_debugging_steps(base) + steps(
                    RailRnaPreprocess.protosteps(base, base.output_dir),
                    base.action_on_failure,
                    base.hadoop_jar, '/mnt/src/rna/steps',
                    reducer_count, base.intermediate_dir, unix=True
                )
        self._json_serial['AmiVersion'] = base.ami_version
        if base.log_uri is not None:
            self._json_serial['LogUri'] = base.log_uri
        else:
            self._json_serial['LogUri'] = path_join(True, base.output_dir,
                                                        'logs')
        self._json_serial['Name'] = base.name
        self._json_serial['NewSupportedProducts'] = []
        self._json_serial['Tags'] = base.tags
        self._json_serial['VisibleToAllUsers'] = (
                'true' if base.visible_to_all_users else 'false'
            )
        self._json_serial['Instances'] = RailRnaCloud.instances(base)
        self._json_serial['BootstrapActions'] \
            = RailRnaPreprocess.bootstrap(base) + RailRnaCloud.bootstrap(base)
    
    @property
    def json_serial(self):
        return self._json_serial

class RailRnaLocalAlignJson:
    """ Constructs JSON for local mode + align job flow. """
    def __init__(self, manifest, output_dir, intermediate_dir='./intermediate',
        force=False, aws_exe=None, profile='default', region='us-east-1',
        verbose=False, bowtie1_exe=None,
        bowtie1_idx='genome', bowtie1_build_exe=None, bowtie2_exe=None,
        bowtie2_build_exe=None, bowtie2_idx='genome',
        bowtie2_args='', samtools_exe=None, bedtobigbed_exe=None,
        genome_partition_length=5000, max_readlet_size=25,
        min_readlet_size=15, readlet_interval=4, cap_size_multiplier=1.2,
        max_intron_size=500000, min_intron_size=10, min_exon_size=9,
        motif_search_window_size=1000, motif_radius=5,
        normalize_percentile=0.75, do_not_output_bam_by_chr=False,
        output_sam=False, bam_basename='alignments', bed_basename='',
        num_processes=1, keep_intermediates=False):
        base = RailRnaErrors(manifest, output_dir, 
            intermediate_dir=intermediate_dir,
            force=force, aws_exe=aws_exe, profile=profile,
            region=region, verbose=verbose)
        RailRnaLocal(base, check_manifest=False, num_processes=num_processes,
            keep_intermediates=keep_intermediates)
        RailRnaAlign(cloud=False, bowtie1_exe=None,
            bowtie1_idx='genome', bowtie1_build_exe=None, bowtie2_exe=None,
            bowtie2_build_exe=None, bowtie2_idx='genome',
            bowtie2_args='', samtools_exe=None, bedtobigbed_exe=None,
            genome_partition_length=5000, max_readlet_size=25,
            min_readlet_size=15, readlet_interval=4, cap_size_multiplier=1.2,
            max_intron_size=500000, min_intron_size=10, min_exon_size=9,
            motif_search_window_size=1000, motif_radius=5,
            normalize_percentile=0.75, do_not_output_bam_by_chr=False,
            output_sam=False, bam_basename='alignments', bed_basename='')
        if base.errors:
            raise RuntimeError(
                    '\n'.join(
                            ['%d) %s' % (i, error) for i, error in errors]
                        )
                )
        self._json_serial = {}
        step_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 
                                                    'steps'))
        self._json_serial['Steps'] = steps(RailRnaAlign.protosteps(base,
                base.output_dir, cloud=False), '', '', step_dir,
                base.num_processes, base.intermediate_dir, unix=False
            )

    @property
    def json_serial(self):
        return self._json_serial

class RailRnaCloudAlignJson:
    """ Constructs JSON for cloud mode + align job flow. """
    def __init__(self, manifest, output_dir, intermediate_dir='./intermediate',
        force=False, aws_exe=None, profile='default', region='us-east-1',
        verbose=False, bowtie1_exe=None, bowtie1_idx='genome',
        bowtie1_build_exe=None, bowtie2_exe=None,
        bowtie2_build_exe=None, bowtie2_idx='genome',
        bowtie2_args='', samtools_exe=None, bedtobigbed_exe=None,
        genome_partition_length=5000, max_readlet_size=25,
        min_readlet_size=15, readlet_interval=4, cap_size_multiplier=1.2,
        max_intron_size=500000, min_intron_size=10, min_exon_size=9,
        motif_search_window_size=1000, motif_radius=5,
        normalize_percentile=0.75, do_not_output_bam_by_chr=False,
        output_sam=False, bam_basename='alignments', bed_basename='',
        log_uri=None, ami_version='2.4.2',
        visible_to_all_users=False, tags='',
        name='Rail-RNA Job Flow',
        action_on_failure='TERMINATE_JOB_FLOW',
        hadoop_jar='/home/hadoop/contrib/streaming/hadoop-streaming-1.0.3.jar',
        master_instance_count=1, master_instance_type='c1.xlarge',
        master_instance_bid_price=None, core_instance_count=1,
        core_instance_type=None, core_instance_bid_price=None,
        task_instance_count=0, task_instance_type=None,
        task_instance_bid_price=None, ec2_key_name=None, keep_alive=False,
        termination_protected=False):
        base = RailRnaErrors(manifest, output_dir, 
            intermediate_dir=intermediate_dir,
            force=force, aws_exe=aws_exe, profile=profile,
            region=region, verbose=verbose)
        RailRnaCloud(base, check_manifest=False,
            log_uri=log_uri, ami_version=ami_version,
            visible_to_all_users=visible_to_all_users, tags=tags,
            name=name,
            action_on_failure=action_on_failure,
            hadoop_jar=hadoop_jar, master_instance_count=master_instance_count,
            master_instance_type=master_instance_type,
            master_instance_bid_price=master_instance_bid_price,
            core_instance_count=core_instance_count,
            core_instance_type=core_instance_type,
            core_instance_bid_price=core_instance_bid_price,
            task_instance_count=task_instance_count,
            task_instance_type=task_instance_type,
            task_instance_bid_price=task_instance_bid_price,
            ec2_key_name=ec2_key_name, keep_alive=keep_alive,
            termination_protected=termination_protected)
        RailRnaAlign(cloud=True, bowtie1_exe=None,
            bowtie1_idx='genome', bowtie1_build_exe=None, bowtie2_exe=None,
            bowtie2_build_exe=None, bowtie2_idx='genome',
            bowtie2_args='', samtools_exe=None, bedtobigbed_exe=None,
            genome_partition_length=5000, max_readlet_size=25,
            min_readlet_size=15, readlet_interval=4, cap_size_multiplier=1.2,
            max_intron_size=500000, min_intron_size=10, min_exon_size=9,
            motif_search_window_size=1000, motif_radius=5,
            normalize_percentile=0.75, do_not_output_bam_by_chr=False,
            output_sam=False, bam_basename='alignments', bed_basename='',
            s3_ansible=ab.S3Ansible(aws_exe=base.aws_exe,
                                        profile=base.profile))
        if base.errors:
            raise RuntimeError(
                    '\n'.join(
                            ['%d) %s' % (i, error) for i, error in errors]
                        )
                )
        self._json_serial = {}
        if base.core_instance_count > 0:
            reducer_count = base.core_instance_count \
                * base.instance_core_counts[base.core_instance_type]
        else:
            reducer_count = base.master_instance_count \
                * base.instance_core_counts[base.core_instance_type]
        self._json_serial['Steps'] \
            = RailRnaCloud.hadoop_debugging_steps(base) + \
                steps(
                    RailRnaAlign.protosteps(base, base.input_dir, cloud=True),
                    base.action_on_failure,
                    base.hadoop_jar, '/mnt/src/rna/steps',
                    reducer_count, base.intermediate_dir, unix=True
                )
        self._json_serial['AmiVersion'] = base.ami_version
        if base.log_uri is not None:
            self._json_serial['LogUri'] = base.log_uri
        else:
            self._json_serial['LogUri'] = path_join(True, base.output_dir,
                                                        'logs')
        self._json_serial['Name'] = base.name
        self._json_serial['NewSupportedProducts'] = []
        self._json_serial['Tags'] = base.tags
        self._json_serial['VisibleToAllUsers'] = (
                'true' if base.visible_to_all_users else 'false'
            )
        self._json_serial['Instances'] = RailRnaCloud.instances(base)
        self._json_serial['BootstrapActions'] \
            = RailRnaPreprocess.bootstrap(base) + RailRnaCloud.bootstrap(base)
    
    @property
    def json_serial(self):
        return self._json_serial

class RailRnaLocalAllJson:
    """ Constructs JSON for local mode + preprocess+align job flow. """
    def __init__(self, manifest, output_dir, intermediate_dir='./intermediate',
        force=False, aws_exe=None, profile='default', region='us-east-1',
        verbose=False, nucleotides_per_input=8000000, gzip_input=True,
        bowtie1_exe=None, bowtie1_idx='genome', bowtie1_build_exe=None,
        bowtie2_exe=None, bowtie2_build_exe=None, bowtie2_idx='genome',
        bowtie2_args='', samtools_exe=None, bedtobigbed_exe=None,
        genome_partition_length=5000, max_readlet_size=25,
        min_readlet_size=15, readlet_interval=4, cap_size_multiplier=1.2,
        max_intron_size=500000, min_intron_size=10, min_exon_size=9,
        motif_search_window_size=1000, motif_radius=5,
        normalize_percentile=0.75, do_not_output_bam_by_chr=False,
        output_sam=False, bam_basename='alignments', bed_basename='',
        num_processes=1, keep_intermediates=False):
        base = RailRnaErrors(manifest, output_dir, 
            intermediate_dir=intermediate_dir,
            force=force, aws_exe=aws_exe, profile=profile,
            region=region, verbose=verbose)
        RailRnaPreprocess(base, nucleotides_per_input=nucleotides_per_input,
            gzip_input=gzip_input)
        RailRnaLocal(base, check_manifest=True, num_processes=num_processes,
            keep_intermediates=keep_intermediates)
        RailRnaAlign(cloud=False, bowtie1_exe=None,
            bowtie1_idx='genome', bowtie1_build_exe=None, bowtie2_exe=None,
            bowtie2_build_exe=None, bowtie2_idx='genome',
            bowtie2_args='', samtools_exe=None, bedtobigbed_exe=None,
            genome_partition_length=5000, max_readlet_size=25,
            min_readlet_size=15, readlet_interval=4, cap_size_multiplier=1.2,
            max_intron_size=500000, min_intron_size=10, min_exon_size=9,
            motif_search_window_size=1000, motif_radius=5,
            normalize_percentile=0.75, do_not_output_bam_by_chr=False,
            output_sam=False, bam_basename='alignments', bed_basename='')
        if base.errors:
            raise RuntimeError(
                    '\n'.join(
                            ['%d) %s' % (i, error) for i, error in errors]
                        )
                )
        self._json_serial = {}
        step_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 
                                                    'steps'))
        middle_dir = os.path.join(base.intermediate_dir, 'preprocess', 'push')
        self._json_serial['Steps'] = \
            steps(RailRnaPreprocess.protosteps(base,
                middle_dir), '', '', step_dir, base.num_processes,
                base.intermediate_dir, unix=False
            ) + \
            steps(RailRnaAlign.protosteps(base,
                middle_dir, cloud=False), '', '', step_dir,
                base.num_processes, base.intermediate_dir, unix=False
            )

    @property
    def json_serial(self):
        return self._json_serial

class RailRnaCloudAllJson:
    """ Constructs JSON for cloud mode + preprocess+align job flow. """
    def __init__(self, manifest, output_dir, intermediate_dir='./intermediate',
        force=False, aws_exe=None, profile='default', region='us-east-1',
        verbose=False, nucleotides_per_input=8000000, gzip_input=True,
        bowtie1_exe=None, bowtie1_idx='genome', bowtie1_build_exe=None,
        bowtie2_exe=None, bowtie2_build_exe=None, bowtie2_idx='genome',
        bowtie2_args='', samtools_exe=None, bedtobigbed_exe=None,
        genome_partition_length=5000, max_readlet_size=25,
        min_readlet_size=15, readlet_interval=4, cap_size_multiplier=1.2,
        max_intron_size=500000, min_intron_size=10, min_exon_size=9,
        motif_search_window_size=1000, motif_radius=5,
        normalize_percentile=0.75, do_not_output_bam_by_chr=False,
        output_sam=False, bam_basename='alignments', bed_basename='',
        log_uri=None, ami_version='2.4.2',
        visible_to_all_users=False, tags='',
        name='Rail-RNA Job Flow',
        action_on_failure='TERMINATE_JOB_FLOW',
        hadoop_jar='/home/hadoop/contrib/streaming/hadoop-streaming-1.0.3.jar',
        master_instance_count=1, master_instance_type='c1.xlarge',
        master_instance_bid_price=None, core_instance_count=1,
        core_instance_type=None, core_instance_bid_price=None,
        task_instance_count=0, task_instance_type=None,
        task_instance_bid_price=None, ec2_key_name=None, keep_alive=False,
        termination_protected=False):
        base = RailRnaErrors(manifest, output_dir, 
            intermediate_dir=intermediate_dir,
            force=force, aws_exe=aws_exe, profile=profile,
            region=region, verbose=verbose)
        RailRnaCloud(base, check_manifest=True, 
            log_uri=log_uri, ami_version=ami_version,
            visible_to_all_users=visible_to_all_users, tags=tags,
            name=name,
            action_on_failure=action_on_failure,
            hadoop_jar=hadoop_jar, master_instance_count=master_instance_count,
            master_instance_type=master_instance_type,
            master_instance_bid_price=master_instance_bid_price,
            core_instance_count=core_instance_count,
            core_instance_type=core_instance_type,
            core_instance_bid_price=core_instance_bid_price,
            task_instance_count=task_instance_count,
            task_instance_type=task_instance_type,
            task_instance_bid_price=task_instance_bid_price,
            ec2_key_name=ec2_key_name, keep_alive=keep_alive,
            termination_protected=termination_protected)
        RailRnaPreprocess(base, nucleotides_per_input=nucleotides_per_input,
            gzip_input=gzip_input)
        RailRnaAlign(cloud=True, bowtie1_exe=None,
            bowtie1_idx='genome', bowtie1_build_exe=None, bowtie2_exe=None,
            bowtie2_build_exe=None, bowtie2_idx='genome',
            bowtie2_args='', samtools_exe=None, bedtobigbed_exe=None,
            genome_partition_length=5000, max_readlet_size=25,
            min_readlet_size=15, readlet_interval=4, cap_size_multiplier=1.2,
            max_intron_size=500000, min_intron_size=10, min_exon_size=9,
            motif_search_window_size=1000, motif_radius=5,
            normalize_percentile=0.75, do_not_output_bam_by_chr=False,
            output_sam=False, bam_basename='alignments', bed_basename='',
            s3_ansible=ab.S3Ansible(aws_exe=base.aws_exe,
                                        profile=base.profile))
        if base.errors:
            raise RuntimeError(
                    '\n'.join(
                            ['%d) %s' % (i, error) for i, error in errors]
                        )
                )
        self._json_serial = {}
        if base.core_instance_count > 0:
            reducer_count = base.core_instance_count \
                * base.instance_core_counts[base.core_instance_type]
        else:
            reducer_count = base.master_instance_count \
                * base.instance_core_counts[base.core_instance_type]
        middle_dir = path_join(True, base.intermediate_dir,
                                        'preprocess', 'push')
        self._json_serial['Steps'] \
            = RailRnaCloud.hadoop_debugging_steps(base) + \
                steps(
                    RailRnaPreprocess.protosteps(base, middle_dir),
                    base.action_on_failure,
                    base.hadoop_jar, '/mnt/src/rna/steps',
                    reducer_count, base.intermediate_dir, unix=True
                ) + \
                steps(
                    RailRnaAlign.protosteps(base, middle_dir, cloud=True),
                    base.action_on_failure,
                    base.hadoop_jar, '/mnt/src/rna/steps',
                    reducer_count, base.intermediate_dir, unix=True
                )
        self._json_serial['AmiVersion'] = base.ami_version
        if base.log_uri is not None:
            self._json_serial['LogUri'] = base.log_uri
        else:
            self._json_serial['LogUri'] = path_join(True, base.output_dir,
                                                        'logs')
        self._json_serial['Name'] = base.name
        self._json_serial['NewSupportedProducts'] = []
        self._json_serial['Tags'] = base.tags
        self._json_serial['VisibleToAllUsers'] = (
                'true' if base.visible_to_all_users else 'false'
            )
        self._json_serial['Instances'] = RailRnaCloud.instances(base)
        self._json_serial['BootstrapActions'] \
            = RailRnaPreprocess.bootstrap(base) + RailRnaCloud.bootstrap(base)
    
    @property
    def json_serial(self):
        return self._json_serial