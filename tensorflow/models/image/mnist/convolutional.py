# Copyright 2015 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

"""Simple, end-to-end, LeNet-5-like convolutional MNIST model example.

This should achieve a test error of 0.7%. Please keep this model as simple and
linear as possible, it is meant as a tutorial for simple convolutional models.
Run with --self_test on the command line to execute a short self-test.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import gzip
import os
import sys
import time

import numpy
from six.moves import urllib
from six.moves import xrange  # pylint: disable=redefined-builtin
import tensorflow as tf

SOURCE_URL = 'http://yann.lecun.com/exdb/mnist/'
WORK_DIRECTORY = 'data'
IMAGE_SIZE = 28
NUM_CHANNELS = 1
PIXEL_DEPTH = 255
NUM_LABELS = 10
VALIDATION_SIZE = 5000  # Size of the validation set.
SEED = 66478  # Set to None for random seed.
BATCH_SIZE = 100
NUM_EPOCHS = 10
EVAL_BATCH_SIZE = 100
EVAL_FREQUENCY = 100  # Number of steps between evaluations.

conv1_patch_size = 5
conv2_patch_size = 5
conv3_patch_size = 5

pool1_width = 2
pool1_height = 2

pool2_width = 2
pool2_height = 2

pool3_width = 2
pool3_height = 2

conv1_output_channels = 32
conv2_output_channels = 64
conv3_output_channels = 128

fc1_depth = 256

tf.app.flags.DEFINE_boolean("self_test", False, "True if running a self test.")
FLAGS = tf.app.flags.FLAGS


def maybe_download(filename):
  """Download the data from Yann's website, unless it's already here."""
  if not tf.gfile.Exists(WORK_DIRECTORY):
    tf.gfile.MakeDirs(WORK_DIRECTORY)
  filepath = os.path.join(WORK_DIRECTORY, filename)
  if not tf.gfile.Exists(filepath):
    filepath, _ = urllib.request.urlretrieve(SOURCE_URL + filename, filepath)
    with tf.gfile.GFile(filepath) as f:
      size = f.Size()
    print('Successfully downloaded', filename, size, 'bytes.')
  return filepath


def extract_data(filename, num_images):
  """Extract the images into a 4D tensor [image index, y, x, channels].

  Values are rescaled from [0, 255] down to [-0.5, 0.5].
  """
  print('Extracting', filename)
  with gzip.open(filename) as bytestream:
    bytestream.read(16)
    buf = bytestream.read(IMAGE_SIZE * IMAGE_SIZE * num_images)
    data = numpy.frombuffer(buf, dtype=numpy.uint8).astype(numpy.float32)
    data = (data - (PIXEL_DEPTH / 2.0)) / PIXEL_DEPTH
    data = data.reshape(num_images, IMAGE_SIZE, IMAGE_SIZE, 1)
    return data


def extract_labels(filename, num_images):
  """Extract the labels into a vector of int64 label IDs."""
  print('Extracting', filename)
  with gzip.open(filename) as bytestream:
    bytestream.read(8)
    buf = bytestream.read(1 * num_images)
    labels = numpy.frombuffer(buf, dtype=numpy.uint8).astype(numpy.int64)
  return labels


def fake_data(num_images):
  """Generate a fake dataset that matches the dimensions of MNIST."""
  data = numpy.ndarray(
      shape=(num_images, IMAGE_SIZE, IMAGE_SIZE, NUM_CHANNELS),
      dtype=numpy.float32)
  labels = numpy.zeros(shape=(num_images,), dtype=numpy.int64)
  for image in xrange(num_images):
    label = image % 2
    data[image, :, :, 0] = label - 0.5
    labels[image] = label
  return data, labels


def error_rate(predictions, labels):
  """Return the error rate based on dense predictions and sparse labels."""
  return 100.0 - (
      100.0 *
      numpy.sum(numpy.argmax(predictions, 1) == labels) /
      predictions.shape[0])


def main(argv=None):  # pylint: disable=unused-argument
  if FLAGS.self_test:
    print('Running self-test.')
    train_data, train_labels = fake_data(256)
    validation_data, validation_labels = fake_data(EVAL_BATCH_SIZE)
    test_data, test_labels = fake_data(EVAL_BATCH_SIZE)
    num_epochs = 1
  else:
    # Get the data.
    train_data_filename = maybe_download('train-images-idx3-ubyte.gz')
    train_labels_filename = maybe_download('train-labels-idx1-ubyte.gz')
    test_data_filename = maybe_download('t10k-images-idx3-ubyte.gz')
    test_labels_filename = maybe_download('t10k-labels-idx1-ubyte.gz')

    # Extract it into numpy arrays.
    train_data = extract_data(train_data_filename, 60000)
    train_labels = extract_labels(train_labels_filename, 60000)
    test_data = extract_data(test_data_filename, 10000)
    test_labels = extract_labels(test_labels_filename, 10000)

    # Generate a validation set.
    validation_data = train_data[:VALIDATION_SIZE, ...]
    validation_labels = train_labels[:VALIDATION_SIZE]
    train_data = train_data[VALIDATION_SIZE:, ...]
    train_labels = train_labels[VALIDATION_SIZE:]
    num_epochs = NUM_EPOCHS
  train_size = train_labels.shape[0]

  # This is where training samples and labels are fed to the graph.
  # These placeholder nodes will be fed a batch of training data at each
  # training step using the {feed_dict} argument to the Run() call below.
  train_data_node = tf.placeholder(
      tf.float32,
      shape=(BATCH_SIZE, IMAGE_SIZE, IMAGE_SIZE, NUM_CHANNELS))
  train_labels_node = tf.placeholder(tf.int64, shape=(BATCH_SIZE,))
  eval_data = tf.placeholder(
      tf.float32,
      shape=(EVAL_BATCH_SIZE, IMAGE_SIZE, IMAGE_SIZE, NUM_CHANNELS))

  # The variables below hold all the trainable weights. They are passed an
  # initial value which will be assigned when we call:
  # {tf.initialize_all_variables().run()}
  fc_height = (IMAGE_SIZE // (pool1_height + pool2_height + pool3_height)) * (
      IMAGE_SIZE // (pool1_width * pool2_width + pool3_width)) * conv3_output_channels
  fc1_weights = tf.Variable(  # fully connected, depth 512.
      tf.truncated_normal(
          [fc_height, fc1_depth],
          stddev=0.1,
          seed=SEED))
  fc1_biases = tf.Variable(tf.constant(0.1, shape=[fc1_depth]))
  fc2_weights = tf.Variable(
      tf.truncated_normal([fc1_depth, NUM_LABELS],
                          stddev=0.1,
                          seed=SEED))
  fc2_biases = tf.Variable(tf.constant(0.1, shape=[NUM_LABELS]))

  # We will replicate the model structure for the training subgraph, as well
  # as the evaluation subgraphs, while sharing the trainable parameters.
  def model(data, train=False):
    """The Model definition."""
    # 2D convolution, with 'SAME' padding (i.e. the output feature map has
    # the same size as the input). Note that {strides} is a 4D array whose
    # shape matches the data layout: [image index, y, x, depth].
    print("data.shape", data.get_shape())
    print("### conv1")
    conv1_weights = tf.Variable(
        tf.truncated_normal([conv1_patch_size, conv1_patch_size, NUM_CHANNELS, conv1_output_channels],
                            stddev=0.1,
                            seed=SEED))
    print("conv1_weights.shape", conv1_weights.get_shape())
    conv1_biases = tf.Variable(tf.zeros([conv1_output_channels]))
    conv1 = tf.nn.conv2d(data,
                        conv1_weights,
                        strides=[1, 1, 1, 1],
                        padding='SAME')
    # Bias and rectified linear non-linearity.
    print("conv1.shape", conv1.get_shape())
    relu1 = tf.nn.relu(tf.nn.bias_add(conv1, conv1_biases))
    print("relu1.shape", relu1.get_shape())
    # Max pooling. The kernel size spec {ksize} also follows the layout of
    # the data. Here we have a pooling window of 2, and a stride of 2.
    pool1 = tf.nn.max_pool(relu1,
                          ksize=[1, pool1_height, pool1_width, 1],
                          strides=[1, pool1_height, pool1_width, 1],
                          padding='SAME')
    print("pool1.shape", pool1.get_shape())
    ###
    print("### conv2")
    conv2_weights = tf.Variable(
        tf.truncated_normal([conv2_patch_size, conv2_patch_size, conv1_output_channels, conv2_output_channels],
                            stddev=0.1,
                            seed=SEED))
    print("conv2_weights.shape", conv2_weights.get_shape())
    conv2_biases = tf.Variable(tf.constant(0.1, shape=[conv2_output_channels]))
    conv2 = tf.nn.conv2d(pool1,
                        conv2_weights,
                        strides=[1, 1, 1, 1],
                        padding='SAME')
    print("conv2.shape", conv2.get_shape())
    relu2 = tf.nn.relu(tf.nn.bias_add(conv2, conv2_biases))
    print("relu2.shape", relu2.get_shape())
    pool2 = tf.nn.max_pool(relu2,
                          ksize=[1, pool2_height, pool2_width, 1],
                          strides=[1, pool2_height, pool2_width, 1],
                          padding='SAME')
    print("pool2.shape", pool2.get_shape())
    ###
    print("### conv3")
    conv3_weights = tf.Variable(
        tf.truncated_normal([conv3_patch_size, conv3_patch_size, conv2_output_channels, conv3_output_channels],
                            stddev=0.1,
                            seed=SEED))
    print("conv3_weights.shape", conv3_weights.get_shape())
    conv3_biases = tf.Variable(tf.constant(0.1, shape=[conv3_output_channels]))
    conv3 = tf.nn.conv2d(pool2,
                        conv3_weights,
                        strides=[1, 1, 1, 1],
                        padding='SAME')
    print("conv3.shape", conv3.get_shape())
    relu3 = tf.nn.relu(tf.nn.bias_add(conv3, conv3_biases))
    print("relu3.shape", relu3.get_shape())
    pool3 = tf.nn.max_pool(relu3,
                          ksize=[1, pool3_height, pool3_width, 1],
                          strides=[1, pool3_height, pool3_width, 1],
                          padding='SAME')
    print("pool3.shape", pool3.get_shape())
    ###
    # Reshape the feature map cuboid into a 2D matrix to feed it to the
    # fully connected layers.
    print("### reshape")
    pool3_shape = pool3.get_shape().as_list()
    reshape = tf.reshape(
        pool3,
        [pool3_shape[0], pool3_shape[1] * pool3_shape[2] * pool3_shape[3]])
    print("reshape.shape", reshape.get_shape())
    print("### Fully connected layer")
    # Fully connected layer. Note that the '+' operation automatically
    # broadcasts the biases.
    # fc1
    print("fc_height", fc_height)
    hidden = tf.nn.relu(tf.matmul(reshape, fc1_weights) + fc1_biases)
    print("hidden.shape", hidden.get_shape())
    # Add a 50% dropout during training only. Dropout also scales
    # activations such that no rescaling is needed at evaluation time.
    if train:
      hidden = tf.nn.dropout(hidden, 0.5, seed=SEED)
    # fc2
    return tf.matmul(hidden, fc2_weights) + fc2_biases

  # Training computation: logits + cross-entropy loss.
  logits = model(train_data_node, True)
  loss = tf.reduce_mean(tf.nn.sparse_softmax_cross_entropy_with_logits(
      logits, train_labels_node))

  # L2 regularization for the fully connected parameters.
  regularizers = (tf.nn.l2_loss(fc1_weights) + tf.nn.l2_loss(fc1_biases) +
                  tf.nn.l2_loss(fc2_weights) + tf.nn.l2_loss(fc2_biases))
  # Add the regularization term to the loss.
  loss += 5e-4 * regularizers

  # Optimizer: set up a variable that's incremented once per batch and
  # controls the learning rate decay.
  batch = tf.Variable(0)
  # Decay once per epoch, using an exponential schedule starting at 0.01.
  learning_rate = tf.train.exponential_decay(
      0.01,                # Base learning rate.
      batch * BATCH_SIZE,  # Current index into the dataset.
      train_size,          # Decay step.
      0.95,                # Decay rate.
      staircase=True)
  # Use simple momentum for the optimization.
  optimizer = tf.train.MomentumOptimizer(learning_rate,
                                         0.9).minimize(loss,
                                                       global_step=batch)

  # Predictions for the current training minibatch.
  train_prediction = tf.nn.softmax(logits)

  # Predictions for the test and validation, which we'll compute less often.
  eval_prediction = tf.nn.softmax(model(eval_data))

  # Small utility function to evaluate a dataset by feeding batches of data to
  # {eval_data} and pulling the results from {eval_predictions}.
  # Saves memory and enables this to run on smaller GPUs.
  def eval_in_batches(data, sess):
    """Get all predictions for a dataset by running it in small batches."""
    size = data.shape[0]
    if size < EVAL_BATCH_SIZE:
      raise ValueError("batch size for evals larger than dataset: %d" % size)
    predictions = numpy.ndarray(shape=(size, NUM_LABELS), dtype=numpy.float32)
    for begin in xrange(0, size, EVAL_BATCH_SIZE):
      end = begin + EVAL_BATCH_SIZE
      if end <= size:
        predictions[begin:end, :] = sess.run(
            eval_prediction,
            feed_dict={eval_data: data[begin:end, ...]})
      else:
        batch_predictions = sess.run(
            eval_prediction,
            feed_dict={eval_data: data[-EVAL_BATCH_SIZE:, ...]})
        predictions[begin:, :] = batch_predictions[begin - size:, :]
    return predictions

  # Create a local session to run the training.
  start_time = time.time()
  with tf.Session() as sess:
    # Run all the initializers to prepare the trainable parameters.
    tf.initialize_all_variables().run()
    print('Initialized!')
    # Loop through training steps.
    for step in xrange(int(num_epochs * train_size) // BATCH_SIZE):
      # Compute the offset of the current minibatch in the data.
      # Note that we could use better randomization across epochs.
      offset = (step * BATCH_SIZE) % (train_size - BATCH_SIZE)
      batch_data = train_data[offset:(offset + BATCH_SIZE), ...]
      batch_labels = train_labels[offset:(offset + BATCH_SIZE)]
      # This dictionary maps the batch data (as a numpy array) to the
      # node in the graph it should be fed to.
      feed_dict = {train_data_node: batch_data,
                   train_labels_node: batch_labels}
      # Run the graph and fetch some of the nodes.
      _, l, lr, predictions = sess.run(
          [optimizer, loss, learning_rate, train_prediction],
          feed_dict=feed_dict)
      if step % EVAL_FREQUENCY == 0:
        elapsed_time = time.time() - start_time
        start_time = time.time()
        print('Step %d (epoch %.2f), %.1f ms' %
              (step, float(step) * BATCH_SIZE / train_size,
               1000 * elapsed_time / EVAL_FREQUENCY))
        print('Minibatch loss: %.3f, learning rate: %.6f' % (l, lr))
        print('Minibatch error: %.1f%%' % error_rate(predictions, batch_labels))
        print('Validation error: %.1f%%' % error_rate(
            eval_in_batches(validation_data, sess), validation_labels))
        sys.stdout.flush()
    # Finally print the result!
    test_error = error_rate(eval_in_batches(test_data, sess), test_labels)
    print('Test error: %.1f%%' % test_error)
    if FLAGS.self_test:
      print('test_error', test_error)
      assert test_error == 0.0, 'expected 0.0 test_error, got %.2f' % (
          test_error,)


if __name__ == '__main__':
  tf.app.run()
