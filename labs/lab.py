#!/usr/bin/env python
#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
# 
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from boto import cloudformation as cfn, sns, vpc
from boto.exception import BotoServerError
import os, sys, json

vpc_provider = "aws"
template = "template.cfn"
max_template_size = 307200

class Lab(object):
	def __init__(self, environment, deployment, region, zone, 
		aws_access_key_id, aws_secret_access_key):
		# Create connections to AWS components
		self.cfn_connection = cfn.connect_to_region(region, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
		self.sns_connection = sns.connect_to_region(region, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
		self.vpc_connection = vpc.connect_to_region(region, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
		
		# Temporary python class -> directory name hack
		lab_dir = self.__class__.__name__.lower()

		self.stack_name = "-".join([lab_dir, environment, deployment, region, zone])
		self.notification_arns = self.get_sns_topic("cloudformation-notifications-" + environment)
		self.parameters = []

		# Prepare the CFN template
		self.template_url = "/".join([os.path.dirname(os.path.realpath(__file__)), lab_dir, vpc_provider, template])
		self.template_body = self.read_file(self.template_url, max_template_size)
		self.validate_template()


	"""
	Create or update an Amazon CloudFormation stack.
	"""
	def deploy(self):
		try:
			if self.stack_exists():
				print "Updating existing '{0}' stack...".format(self.stack_name)
				stack = self.cfn_connection.update_stack(self.stack_name,
					template_body=self.template_body, parameters=self.parameters)
			else:
				print "Creating new '{0}' stack...".format(self.stack_name)
				stack = self.cfn_connection.create_stack(self.stack_name, 
					template_body=self.template_body, parameters=self.parameters,
					notification_arns=self.notification_arns, disable_rollback=True)
		except BotoServerError as e:
			print "({0}) {1}:\n{2}\nError deploying.".format(e.status, e.reason, e.body)
			sys.exit(1)
		print "Stack deployed."
		return stack

	"""
	Determines if a CloudFormation stack exists for a stack name.
	"""
	def stack_exists(self):
		try:
			self.cfn_connection.describe_stacks(stack_name_or_id=self.stack_name)
			return True
		except:
			return False

	"""
	Validates a CloudFormation (CFN) template. 
	If there is an error, communicate the reason and exit (1).
	"""
	def validate_template(self):
		try:
			self.cfn_connection.validate_template(template_body=self.template_body)
			print "Template successfully validated."
		except BotoServerError as e:
			print "({0}) {1}:\n{2}\nError during template validation.".format(e.status, e.reason, e.body)
			sys.exit(1)

	"""
	Read up to max_size bytes from a file and return it as a string.
	"""
	def read_file(self, url, max_size):
		fd = os.open(self.template_url, os.O_RDONLY)
		file_contents = os.read(fd, max_size)
		os.close(fd)
		return file_contents

	"""
	Given a Simple Notification Service (SNS) topic name, return the topic's ARN.
	"""
	def get_sns_topic(self, topic_name):
		for topic in self.sns_connection.get_all_topics()['ListTopicsResponse']['ListTopicsResult']['Topics']:
			if topic_name in topic['TopicArn']:
				return topic['TopicArn']
		return None

	"""
	Given a name, return a Virtual Private Cloud (VPC).
	"""
	def get_vpc(self, vpc_name):
		for vpc in self.vpc_connection.get_all_vpcs():
			try:
				if vpc.tags['Name'] == vpc_name:
					return vpc
			except KeyError:
				continue
		return None

	"""
	Find a subnet by name within a specific VPC and availability zone.
	"""
	def get_subnet(self, subnet_name, vpc_id, zone):
		for subnet in self.vpc_connection.get_all_subnets(filters=[("vpcId", vpc_id), ("availabilityZone", zone)]):
			try:
				if subnet.tags['Name'] == subnet_name:
					return subnet
			except KeyError:
				continue
		return None
