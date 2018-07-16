
import numpy as np
import tensorflow as tf

FLAGS = tf.app.flags.FLAGS

def complex_add(x, y):
    xr, xi = tf.real(x), tf.imag(x)
    yr, yi = tf.real(y), tf.imag(y)
    return tf.complex(xr + yr, xi + yi)

def complex_mul(x, y):
    xr, xi = tf.real(x), tf.imag(x)
    yr, yi = tf.real(y), tf.imag(y)
    return tf.complex(xr*yr - xi*yi, xr*yi + xi*yr)

def stack_k(x, axis, k):

    list_x = []
    for i in range(k):
        list_x.append(x)

    out = tf.stack(list_x, axis)

    return out

'''
##coil_sens = m x n x 2 x C
##x = batch_size x m x n x 2

#Downsampling with coil sensitivities
def downsample(x, mask, coil_sens):

    shape_coil_sens = tf.size(coil_sens)
    num_coil = shape_coil_sens[3]
    x = tf.complex(x[:,:,:,0], x[:,:,:,1])
    mask_kspace = tf.cast(mask, tf.complex64)

    data_kspace = []
    for c in range(num_coil):

          coil_sens_c_complex = tf.complex(coil_sens[:,:,0,c], coil_sens[:,:,1,c])
          coil_sens_c_complex_stack = stack_k(coil_sens_c_complex, axis=0, k=FLAGS.batch_size)
          data_kspace_c = mask_kspace * tf.fft2d(complex_mul(x, coil_sens_c_complex_cat))
          data_kspace.append(data_kspace_c)


    return data_kspace


#Upsampling with coil sensitivites
def upsample(x, mask, coil_sens):

    shape_coil_sens = tf.shape(coil_sens)
    num_coil = shape_coil_sens[3]
    image_complex = tf.zeros([FLAGS.batch_size,shape_coil_sens[0],shape_coil_sens[1]])

    for c in range(num_coil):

        data_kspace_c = tf.reshape(data_kspace[:,:,:,c], [FLAGS.batch_size,shape_coil_sens[0],shape_coil_sens[1]])
        coil_sens_c = coil_sens[c]
        coil_sens_c_complex = tf.complex(coil_sens_c[:,:,0], coil_sens_c[:,:,1])
        coil_sens_c_complex_stack = stack_k(coil_sens_c_complex, axis=0, k=FLAGS.batch_size)
        image_complex_c = tf.conj(coil_sens_c_complex_stack) * tf.ifft2d(data_kspace_c)    #fix the shape for multiplication
        image_complex = tf.add(image_complex, image_complex_c)

    out = tf.concat([tf.real(image_complex), tf.imag(image_complex)], 3)

    return out
'''


#DOWNSAMPLING
#DOWNSAMPLING
def downsample(x, mask):

    mask_kspace = tf.cast(mask, tf.complex64)
    data_kspace = Fourier(x, separate_complex=True)
    out = mask_kspace * data_kspace

    return out


#UPSAMPLING
def upsample(x, mask):

    image_complex = tf.ifft2d(x)
    image_size = [FLAGS.batch_size, FLAGS.sample_size, FLAGS.sample_size_y] #tf.shape(image_complex)

    #get real and imaginary parts
    image_real = tf.reshape(tf.real(image_complex), [image_size[0], image_size[1], image_size[2], 1])
    image_imag = tf.reshape(tf.imag(image_complex), [image_size[0], image_size[1], image_size[2], 1])

    out = tf.concat([image_real, image_imag], 3)

    return out



class Model:
    """A neural network model.

    Currently only supports a feedforward architecture."""
    
    def __init__(self, name, features):
        self.name = name
        self.outputs = [features]

    def _get_layer_str(self, layer=None):
        if layer is None:
            layer = self.get_num_layers()
        
        return '%s_L%03d' % (self.name, layer+1)

    def _get_num_inputs(self):
        return int(self.get_output().get_shape()[-1])

    def _glorot_initializer(self, prev_units, num_units, stddev_factor=1.0):
        """Initialization in the style of Glorot 2010.

        stddev_factor should be 1.0 for linear activations, and 2.0 for ReLUs"""
        stddev  = np.sqrt(stddev_factor / np.sqrt(prev_units*num_units))
        return tf.truncated_normal([prev_units, num_units],
                                    mean=0.0, stddev=stddev)

    def _glorot_initializer_conv2d(self, prev_units, num_units, mapsize, stddev_factor=1.0):
        """Initialization in the style of Glorot 2010.

        stddev_factor should be 1.0 for linear activations, and 2.0 for ReLUs"""

        stddev  = np.sqrt(stddev_factor / (np.sqrt(prev_units*num_units)*mapsize*mapsize))
        return tf.truncated_normal([mapsize, mapsize, prev_units, num_units],
                                    mean=0.0, stddev=stddev)

    def get_num_layers(self):
        return len(self.outputs)

    def add_batch_norm(self, scale=False):
        """Adds a batch normalization layer to this model.

        See ArXiv 1502.03167v3 for details."""

        # TBD: This appears to be very flaky, often raising InvalidArgumentError internally
        with tf.variable_scope(self._get_layer_str()):
            out = tf.contrib.layers.batch_norm(self.get_output(), scale=scale)
        
        self.outputs.append(out)
        return self

    def add_flatten(self):
        """Transforms the output of this network to a 1D tensor"""

        with tf.variable_scope(self._get_layer_str()):
            batch_size = int(self.get_output().get_shape()[0])
            out = tf.reshape(self.get_output(), [batch_size, -1])

        self.outputs.append(out)
        return self

    def add_dense(self, num_units, stddev_factor=1.0):
        """Adds a dense linear layer to this model.

        Uses Glorot 2010 initialization assuming linear activation."""
        
        assert len(self.get_output().get_shape()) == 2, "Previous layer must be 2-dimensional (batch, channels)"

        with tf.variable_scope(self._get_layer_str()):
            prev_units = self._get_num_inputs()
            
            # Weight term
            initw   = self._glorot_initializer(prev_units, num_units,
                                               stddev_factor=stddev_factor)
            weight  = tf.get_variable('weight', initializer=initw)

            # Bias term
            initb   = tf.constant(0.0, shape=[num_units])
            bias    = tf.get_variable('bias', initializer=initb)

            # Output of this layer
            out     = tf.matmul(self.get_output(), weight) + bias

        self.outputs.append(out)
        return self

    def add_sigmoid(self):
        """Adds a sigmoid (0,1) activation function layer to this model."""

        with tf.variable_scope(self._get_layer_str()):
            prev_units = self._get_num_inputs()
            out = tf.nn.sigmoid(self.get_output())
        
        self.outputs.append(out)
        return self

    def add_softmax(self):
        """Adds a softmax operation to this model"""

        with tf.variable_scope(self._get_layer_str()):
            this_input = tf.square(self.get_output())
            reduction_indices = list(range(1, len(this_input.get_shape())))
            acc = tf.reduce_sum(this_input, reduction_indices=reduction_indices, keep_dims=True)
            out = this_input / (acc+FLAGS.epsilon)
            #out = tf.verify_tensor_all_finite(out, "add_softmax failed; is sum equal to zero?")
        
        self.outputs.append(out)
        return self

    def add_relu(self):
        """Adds a ReLU activation function to this model"""

        with tf.variable_scope(self._get_layer_str()):
            out = tf.nn.relu(self.get_output())

        self.outputs.append(out)
        return self        

    def add_elu(self):
        """Adds a ELU activation function to this model"""

        with tf.variable_scope(self._get_layer_str()):
            out = tf.nn.elu(self.get_output())

        self.outputs.append(out)
        return self      

    def add_lrelu(self, leak=.2):
        """Adds a leaky ReLU (LReLU) activation function to this model"""

        with tf.variable_scope(self._get_layer_str()):
            t1  = .5 * (1 + leak)
            t2  = .5 * (1 - leak)
            out = t1 * self.get_output() + \
                  t2 * tf.abs(self.get_output())
            
        self.outputs.append(out)
        return self

    def add_conv2d(self, num_units, mapsize=1, stride=1, stddev_factor=1.0):
        """Adds a 2D convolutional layer."""

        assert len(self.get_output().get_shape()) == 4 and "Previous layer must be 4-dimensional (batch, width, height, channels)"
        
        with tf.variable_scope(self._get_layer_str()):
            prev_units = self._get_num_inputs()
            
            # Weight term and convolution
            initw  = self._glorot_initializer_conv2d(prev_units, num_units,
                                                     mapsize,
                                                     stddev_factor=stddev_factor)
            weight = tf.get_variable('weight', initializer=initw)
            out    = tf.nn.conv2d(self.get_output(), weight,
                                  strides=[1, stride, stride, 1],
                                  padding='SAME')

            # Bias term
            initb  = tf.constant(0.0, shape=[num_units])
            bias   = tf.get_variable('bias', initializer=initb)
            out    = tf.nn.bias_add(out, bias)  #?????!!!
            
        self.outputs.append(out)
        return self


    def add_fullconnect2d(self, num_units, stddev_factor=1.0):
        """Adds a 2D convolutional layer."""

        assert len(self.get_output().get_shape()) == 4 and "Previous layer must be 4-dimensional (batch, width, height, channels)"
        
        with tf.variable_scope(self._get_layer_str()):
            prev_units = self._get_num_inputs()
            
            # Weight term and full connection
            #initw  = self._glorot_initializer_conv2d(prev_units, num_units,
                                                     #mapsize,
                                                     #stddev_factor=stddev_factor)
            weight = tf.get_variable('weight', initializer=initw)
            out = tf.contrib.layers.fully_connected(self.get_output(), num_units, activation_fn=None, normalizer_fn=None, normalizer_params=None, 
                                                    weights_initializer=initializers.xavier_initializer(),
                                                    weights_regularizer=None,
                                                    biases_initializer=tf.zeros_initializer(),
                                                    biases_regularizer=None,
                                                    reuse=None,
                                                    variables_collections=None,
                                                    outputs_collections=None,
                                                    trainable=True,
                                                    scope=None)    #activation_fn=tf.nn.relu


            #out    = tf.nn.conv2d(self.get_output(), weight,
                                  #strides=[1, stride, stride, 1],
                                  #padding='SAME')

            # Bias term
            initb  = tf.constant(0.0, shape=[num_units])
            bias   = tf.get_variable('bias', initializer=initb)
            out    = tf.nn.bias_add(out, bias)
            
        self.outputs.append(out)
        return self


    def add_conv2d_transpose(self, num_units, mapsize=1, stride=1, stddev_factor=1.0):
        """Adds a transposed 2D convolutional layer"""

        assert len(self.get_output().get_shape()) == 4 and "Previous layer must be 4-dimensional (batch, width, height, channels)"

        with tf.variable_scope(self._get_layer_str()):
            prev_units = self._get_num_inputs()
            
            # Weight term and convolution
            initw  = self._glorot_initializer_conv2d(prev_units, num_units,
                                                     mapsize,
                                                     stddev_factor=stddev_factor)
            weight = tf.get_variable('weight', initializer=initw)
            weight = tf.transpose(weight, perm=[0, 1, 3, 2])
            prev_output = self.get_output()
            output_shape = [FLAGS.batch_size,
                            int(prev_output.get_shape()[1]) * stride,
                            int(prev_output.get_shape()[2]) * stride,
                            num_units]
            out = tf.nn.conv2d_transpose(self.get_output(), weight,
                                            output_shape=output_shape,
                                            strides=[1, stride, stride, 1],
                                            padding='SAME')

            # Bias term
            initb  = tf.constant(0.0, shape=[num_units])
            bias   = tf.get_variable('bias', initializer=initb)
            out    = tf.nn.bias_add(out, bias)
            
        self.outputs.append(out)
        return self

    def add_residual_block(self, num_units, mapsize=3, num_layers=2, stddev_factor=1e-3):
        """Adds a residual block as per Arxiv 1512.03385, Figure 3"""

        assert len(self.get_output().get_shape()) == 4 and "Previous layer must be 4-dimensional (batch, width, height, channels)"

        # Add projection in series if needed prior to shortcut
        if num_units != int(self.get_output().get_shape()[3]):
            self.add_conv2d(num_units, mapsize=1, stride=1, stddev_factor=1.)

        bypass = self.get_output()

        # Residual block
        for _ in range(num_layers):
            self.add_batch_norm()
            self.add_relu()
            self.add_conv2d(num_units, mapsize=mapsize, stride=1, stddev_factor=stddev_factor)

        self.add_sum(bypass)

        return self

    def add_bottleneck_residual_block(self, num_units, mapsize=3, stride=1, transpose=False):
        """Adds a bottleneck residual block as per Arxiv 1512.03385, Figure 3"""

        assert len(self.get_output().get_shape()) == 4 and "Previous layer must be 4-dimensional (batch, width, height, channels)"

        # Add projection in series if needed prior to shortcut
        if num_units != int(self.get_output().get_shape()[3]) or stride != 1:
            ms = 1 if stride == 1 else mapsize
            #bypass.add_batch_norm() # TBD: Needed?
            if transpose:
                self.add_conv2d_transpose(num_units, mapsize=ms, stride=stride, stddev_factor=1.)
            else:
                self.add_conv2d(num_units, mapsize=ms, stride=stride, stddev_factor=1.)

        bypass = self.get_output()

        # Bottleneck residual block
        self.add_batch_norm()
        self.add_relu()
        self.add_conv2d(num_units//4, mapsize=1,       stride=1,      stddev_factor=2.)

        self.add_batch_norm()
        self.add_relu()
        if transpose:
            self.add_conv2d_transpose(num_units//4,
                                      mapsize=mapsize,
                                      stride=1,
                                      stddev_factor=2.)
        else:
            self.add_conv2d(num_units//4,
                            mapsize=mapsize,
                            stride=1,
                            stddev_factor=2.)

        self.add_batch_norm()
        self.add_relu()
        self.add_conv2d(num_units,    mapsize=1,       stride=1,      stddev_factor=2.)

        self.add_sum(bypass)

        return self

    def add_sum(self, term):
        """Adds a layer that sums the top layer with the given term"""

        with tf.variable_scope(self._get_layer_str()):
            prev_shape = self.get_output().get_shape()
            term_shape = term.get_shape()
            #print("%s %s" % (prev_shape, term_shape))
            assert prev_shape == term_shape and "Can't sum terms with a different size"
            out = tf.add(self.get_output(), term)
        
        self.outputs.append(out)
        return self


    def add_dense(self, num_units, stddev_factor=1.0):
        """Adds a dense linear layer to this model.

        Uses Glorot 2010 initialization assuming linear activation."""
        
        assert len(self.get_output().get_shape()) == 2, "Previous layer must be 2-dimensional (batch, channels)"

        with tf.variable_scope(self._get_layer_str()):
            prev_units = self._get_num_inputs()
            
            # Weight term
            initw   = self._glorot_initializer(prev_units, num_units,
                                               stddev_factor=stddev_factor)
            weight  = tf.get_variable('weight', initializer=initw)

            # Bias term
            initb   = tf.constant(0.0, shape=[num_units])
            bias    = tf.get_variable('bias', initializer=initb)

            # Output of this layer
            out     = tf.matmul(self.get_output(), weight) + bias

        self.outputs.append(out)
        return self


    def add_scale(self, stddev_factor=1.0):

        """Adds a layer that scales the top layer with the given term"""
        with tf.variable_scope(self._get_layer_str()):
            
            # Weight term
            initw = self._glorot_initializer(1, 1,
                                               stddev_factor=stddev_factor)
            weight = tf.get_variable('weight', initializer=initw)

            # Output of this layer
            out = tf.scalar_mul(weight[0,0], self.get_output())

        self.outputs.append(out)
        return self


    def add_mean(self):
        """Adds a layer that averages the inputs from the previous layer"""

        with tf.variable_scope(self._get_layer_str()):
            prev_shape = self.get_output().get_shape()
            reduction_indices = list(range(len(prev_shape)))
            assert len(reduction_indices) > 2 and "Can't average a (batch, activation) tensor"
            reduction_indices = reduction_indices[1:-1]
            out = tf.reduce_mean(self.get_output(), reduction_indices=reduction_indices)
        
        self.outputs.append(out)
        return self

    def add_upscale(self, size=None):
        """Adds a layer that upscales the output by 2x through nearest neighbor interpolation"""

        prev_shape = self.get_output().get_shape()
        if size is None:
            size = [2 * int(s) for s in prev_shape[1:3]]
        out  = tf.image.resize_nearest_neighbor(self.get_output(), size)

        self.outputs.append(out)
        return self    

    def add_upsample(self, mask):
        """Adds a layer that upsamples the output by Kx through transpose convolution"""

        prev_shape = self.get_output().get_shape()
        out = upsample(self.get_output(), mask)

        self.outputs.append(out)
        return self

    def add_downsample(self, mask):
        """Adds a layer that downsamples the output by Kx through transpose convolution"""

        prev_shape = self.get_output().get_shape()
        out = downsample(self.get_output(), mask)

        self.outputs.append(out)
        return self


    def add_concat(self, layer_add):
        last_layer = self.get_output()
        prev_shape = last_layer.get_shape()
        try:
            out = tf.concat(axis = 3, values = [last_layer, layer_add])
            self.outputs.append(out)
        except:
            print('fail to concat {0} and {1}'.format(last_layer, layer_add))
        return self    

    def add_layer(self, layer_add):
        self.outputs.append(layer_add)
        return self 


    def get_output(self):
        """Returns the output from the topmost layer of the network"""
        return self.outputs[-1]

    def get_variable(self, layer, name):
        """Returns a variable given its layer and name.

        The variable must already exist."""

        scope      = self._get_layer_str(layer)
        collection = tf.get_collection(tf.GraphKeys.VARIABLES, scope=scope)

        # TBD: Ugly!
        for var in collection:
            if var.name[:-2] == scope+'/'+name:
                return var

        return None

    def get_all_layer_variables(self, layer):
        """Returns all variables in the given layer"""
        scope = self._get_layer_str(layer)
        return tf.get_collection(tf.GraphKeys.VARIABLES, scope=scope)


    def gradients_out_in(output,input_img):
        return tf.gradients(output, input_img)




def _discriminator_model(sess, features, disc_input, layer_output_skip=5, hybrid_disc=0):

    # update 05092017, hybrid_disc consider whether to use hybrid space for discriminator
    # to study the kspace distribution/smoothness properties

    # Fully convolutional model
    mapsize = 3
    layers  = [8,16,32,64]   #[64, 128, 256, 512]   #[8,16]   #[8, 16, 32, 64]#

    old_vars = tf.global_variables()#tf.all_variables() , all_variables() are deprecated

    # augment data to hybrid domain = image+kspace
    if hybrid_disc>0:
        disc_size = tf.shape(disc_input)#disc_input.get_shape()
        # print(disc_size)        
        disc_kspace = Fourier(disc_input, separate_complex=False)
        disc_kspace_real = tf.cast(tf.real(disc_kspace), tf.float32)
        # print(disc_kspace_real)
        disc_kspace_real = tf.reshape(disc_kspace_real, [disc_size[0],disc_size[1],disc_size[2],1])
        disc_kspace_imag = tf.cast(tf.imag(disc_kspace), tf.float32)
        # print(disc_kspace_imag)        
        disc_kspace_imag = tf.reshape(disc_kspace_imag, [disc_size[0],disc_size[1],disc_size[2],1])
        disc_kspace_mag = tf.cast(tf.abs(disc_kspace), tf.float32)
        # print(disc_kspace_mag)
        disc_kspace_mag = tf.log(disc_kspace_mag)
        disc_kspace_mag = tf.reshape(disc_kspace_mag, [disc_size[0],disc_size[1],disc_size[2],1])
        if hybrid_disc == 1:
            disc_hybird = tf.concat(axis = 3, values = [disc_input * 2-1, disc_kspace_imag])
        else:
            disc_hybird = tf.concat(axis = 3, values = [disc_input * 2-1, disc_kspace_imag, disc_kspace_real, disc_kspace_imag])
    else:
        disc_hybird = disc_input #2 * disc_input - 1


    print('shape_disc_hybrid', disc_hybird.get_shape())

    print(hybrid_disc, 'discriminator input dimensions: {0}'.format(disc_hybird.get_shape()))
    model = Model('DIS', disc_hybird)        

    for layer in range(len(layers)):
        nunits = layers[layer]
        stddev_factor = 2.0

        model.add_conv2d(nunits, mapsize=mapsize, stride=2, stddev_factor=stddev_factor)
        model.add_batch_norm()
        model.add_relu()

    # Finalization a la "all convolutional net"
    model.add_conv2d(nunits, mapsize=mapsize, stride=1, stddev_factor=stddev_factor)
    model.add_batch_norm()
    model.add_relu()

    model.add_conv2d(nunits, mapsize=1, stride=1, stddev_factor=stddev_factor)
    model.add_batch_norm()
    model.add_relu()

    # Linearly map to real/fake and return average score
    # (softmax will be applied later)
    model.add_conv2d(1, mapsize=1, stride=1, stddev_factor=stddev_factor)  #1 for magnitude input images
    model.add_mean()

    new_vars  = tf.global_variables()#tf.all_variables() , all_variables() are deprecated
    disc_vars = list(set(new_vars) - set(old_vars))

    #select output
    output_layers = model.outputs[0:]  #[model.outputs[0]] + model.outputs[1:-1][::layer_output_skip] + [model.outputs[-1]]

    return model.get_output(), disc_vars, output_layers

def conv(batch_input, out_channels, stride=2, size_kernel=4):
    with tf.variable_scope("conv"):
        in_channels = batch_input.get_shape()[3]
        filter = tf.get_variable("filter", [size_kernel, size_kernel, in_channels, out_channels], dtype=tf.float32, initializer=tf.random_normal_initializer(0, 0.02))
        # [batch, in_height, in_width, in_channels], [filter_width, filter_height, in_channels, out_channels]
        #     => [batch, out_height, out_width, out_channels]
        padded_input = tf.pad(batch_input, [[0, 0], [1, 1], [1, 1], [0, 0]], mode="CONSTANT")
        conv = tf.nn.conv2d(padded_input, filter, [1, stride, stride, 1], padding="VALID")
        return conv

def deconv(batch_input, out_channels, size_kernel=3):
    with tf.variable_scope("deconv"):
        batch, in_height, in_width, in_channels = [int(d) for d in batch_input.get_shape()]
        filter = tf.get_variable("filter", [size_kernel, size_kernel, out_channels, in_channels], dtype=tf.float32, initializer=tf.random_normal_initializer(0, 0.02))
        # [batch, in_height, in_width, in_channels], [filter_width, filter_height, out_channels, in_channels]
        #     => [batch, out_height, out_width, out_channels]
        conv = tf.nn.conv2d_transpose(batch_input, filter, [batch, in_height * 2, in_width * 2, out_channels], [1, 2, 2, 1], padding="SAME")
        return conv        

def lrelu(x, a):
    with tf.name_scope("lrelu"):
        # adding these together creates the leak part and linear part
        # then cancels them out by subtracting/adding an absolute value term
        # leak: a*x/2 - a*abs(x)/2
        # linear: x/2 + abs(x)/2

        # this block looks like it has 2 inputs on the graph unless we do this
        x = tf.identity(x)
        return (0.5 * (1 + a)) * x + (0.5 * (1 - a)) * tf.abs(x)

def batchnorm(input):
    with tf.variable_scope("batchnorm"):
        # this block looks like it has 3 inputs on the graph unless we do this
        input = tf.identity(input)

        channels = input.get_shape()[3]
        offset = tf.get_variable("offset", [channels], dtype=tf.float32, initializer=tf.zeros_initializer())
        scale = tf.get_variable("scale", [channels], dtype=tf.float32, initializer=tf.random_normal_initializer(1.0, 0.02))
        mean, variance = tf.nn.moments(input, axes=[0, 1, 2], keep_dims=False)
        variance_epsilon = 1e-5
        normalized = tf.nn.batch_normalization(input, mean, variance, offset, scale, variance_epsilon=variance_epsilon)
        return normalized      

def Fourier(x, separate_complex=True):    
    x = tf.cast(x, tf.complex64)
    if separate_complex:
        x_complex = x[:,:,:,0]+1j*x[:,:,:,1]
    else:
        x_complex = x
    x_complex = tf.reshape(x_complex,x_complex.get_shape()[:3])
    y_complex = tf.fft2d(x_complex)
    print('using Fourier, input dim {0}, output dim {1}'.format(x.get_shape(), y_complex.get_shape()))
    # x = tf.cast(x, tf.complex64)
    # y = tf.fft3d(x)
    # y = y[:,:,:,-1]
    return y_complex



def _generator_encoder_decoder(sess, features, labels, masks,channels = 2, layer_output_skip=5):
    print('use encoder decoder model')
    # old variables
    layers = []    
    old_vars = tf.global_variables()#tf.all_variables() , all_variables() are deprecated
    # layers.append(features)

    # definition
    num_filter_generator = 8
    layer_specs = [ 
        num_filter_generator * 2, # encoder_2: [batch, 128, 128, ngf] => [batch, 64, 64, ngf * 2]
        num_filter_generator * 4, # encoder_3: [batch, 64, 64, ngf * 2] => [batch, 32, 32, ngf * 4]
        num_filter_generator * 8, # encoder_4: [batch, 32, 32, ngf * 4] => [batch, 16, 16, ngf * 8]
        # num_filter_generator * 8, # encoder_5: [batch, 16, 16, ngf * 8] => [batch, 8, 8, ngf * 8]
        # num_filter_generator * 8, # encoder_6: [batch, 8, 8, ngf * 8] => [batch, 4, 4, ngf * 8]
        # num_filter_generator * 8, # encoder_7: [batch, 4, 4, ngf * 8] => [batch, 2, 2, ngf * 8]
        num_filter_generator * 16, # encoder_8: [batch, 2, 2, ngf * 8] => [batch, 1, 1, ngf * 8]
    ]

   # encoder_1: [batch, 256, 256, in_channels] => [batch, 128, 128, ngf]
    with tf.variable_scope("encoder_1"):
        output = conv(features, num_filter_generator, stride=2)
        layers.append(output)

    for out_channels in layer_specs:
        with tf.variable_scope("encoder_%d" % (len(layers) + 1)):
            rectified = lrelu(layers[-1], 0.2)
            # [batch, in_height, in_width, in_channels] => [batch, in_height/2, in_width/2, out_channels]
            convolved = conv(rectified, out_channels, stride=2)
            output = batchnorm(convolved)
            layers.append(output)

    
    ###  LATENT SPACE

    #latent_code = layers[-1]
    #print("Latent code shape is:")
    #print(latent_code.shape)






    ###


    layer_specs = [
        # (num_filter_generator * 16, 0.5),   # decoder_8: [batch, 1, 1, ngf * 8] => [batch, 2, 2, ngf * 8 * 2]
        # (num_filter_generator * 8, 0.5),   # decoder_7: [batch, 2, 2, ngf * 8 * 2] => [batch, 4, 4, ngf * 8 * 2]
        # (num_filter_generator * 8, 0.5),   # decoder_6: [batch, 4, 4, ngf * 8 * 2] => [batch, 8, 8, ngf * 8 * 2]
        (num_filter_generator * 8, 0.0),   # decoder_5: [batch, 8, 8, ngf * 8 * 2] => [batch, 16, 16, ngf * 8 * 2]
        (num_filter_generator * 4, 0.0),   # decoder_4: [batch, 16, 16, ngf * 8 * 2] => [batch, 32, 32, ngf * 4 * 2]
        (num_filter_generator * 2, 0.0),   # decoder_3: [batch, 32, 32, ngf * 4 * 2] => [batch, 64, 64, ngf * 2 * 2]
        (num_filter_generator, 0.0),       # decoder_2: [batch, 64, 64, ngf * 2 * 2] => [batch, 128, 128, ngf * 2]
    ]

    num_encoder_layers = len(layers)
    for decoder_layer, (out_channels, dropout) in enumerate(layer_specs):
        skip_layer = num_encoder_layers - decoder_layer - 1
        with tf.variable_scope("decoder_%d" % (skip_layer + 1)):
            if decoder_layer == 0:
                # first decoder layer doesn't have skip connections
                # since it is directly connected to the skip_layer
                input = layers[-1]
            else:
                input = tf.concat(axis=3, values=[layers[-1], layers[skip_layer]]) # change the order of value and axisn, axis=3)

            rectified  = tf.nn.relu(input)
            # [batch, in_height, in_width, in_channels] => [batch, in_height*2, in_width*2, out_channels]
            output = deconv(rectified, out_channels)
            output = batchnorm(output)

            # if dropout > 0.0:
            #     output = tf.nn.dropout(output, keep_prob = 1 - dropout)

            layers.append(output)

    # decoder_1: [batch, 128, 128, ngf * 2] => [batch, 256, 256, generator_outputs_channels]



    with tf.variable_scope("decoder_1"):
        input = tf.concat(axis=3, values=[layers[-1], layers[0]]) #, axis=3)
       #rectified = tf.nn.relu(input)
        #output = deconv(rectified, channels)
        output = deconv(input,channels)
        #output = tf.nn.sigmoid(output)
        layers.append(output)

    for x in layers:
        print(x)

    #hard data consistency

    
    masks_comp = 1.0 - masks
    correct_kspace = downsample(labels, masks) + downsample(layers[-1], masks_comp)
    correct_image = upsample(correct_kspace, masks)
    layers.append(correct_image)
    #layers[-1] = layers[-1] * correct_image
    #print("Dimensions")
    #print(correct_image.shape)
    #model.add_layer(correct_image)


    # out variables
    new_vars  = tf.global_variables()#tf.all_variables() , all_variables() are deprecated
    gene_vars = list(set(new_vars) - set(old_vars))

    # select subset of layers
    output_layers = [layers[0]] + layers[1:-1][::layer_output_skip] + [layers[-1]]

    #adversarial_gradients = gradients_out_in(layers[-1],features)


    return layers[-1], gene_vars, output_layers



"""

def _generator_model_with_pool(sess, features, labels, channels, layer_output_skip=5):
    mapsize = 3
    res_units  = [64, 128, 128] #[64, 32, 16]#[256, 128, 96]
    layer_pooling = [1, 1, 0]
    print('use resnet conv-decov with pooling parameters:', res_units, layer_pooling)
    
    old_vars = tf.global_variables()#tf.all_variables() , all_variables() are deprecated

    # See Arxiv 1603.05027
    model = Model('GEN', features)
    list_layer_before_pool=[]
    for index_layer in range(len(res_units)-1):
        nunits  = res_units[index_layer]

        for j in range(2):
            model.add_residual_block(nunits, mapsize=mapsize)

        list_layer_before_pool.append(model.outputs[-1])
        
        # conv 
        # model.add_batch_norm()
        # model.add_relu()
        # model.add_conv2d_transpose(nunits, mapsize=mapsize, stride=1, stddev_factor=1.)
        model.add_batch_norm()
        model.add_relu()

        # pooling/striding
        stride = layer_pooling[index_layer]+1
        model.add_conv2d(nunits, mapsize=mapsize, stride=stride, stddev_factor=1.)

    print('list_layer_before_pool', list_layer_before_pool)
    print('model.outputs', model.outputs)

    for index_layer_rev in range(len(res_units)-1):
        index_layer = len(list_layer_before_pool)-1-index_layer_rev
        nunits  = res_units[index_layer]

        for j in range(2):
            model.add_residual_block(nunits, mapsize=mapsize)

        # up-pool cov
        if layer_pooling[index_layer]:
            model.add_upscale()

        model.add_batch_norm()
        model.add_relu()
        model.add_conv2d_transpose(nunits, mapsize=mapsize, stride=1, stddev_factor=1.)

        # concat
        model.add_concat(list_layer_before_pool[index_layer])
        

    # conv 
    nunits = res_units[-1]
    model.add_conv2d(nunits, mapsize=mapsize, stride=1, stddev_factor=2.)
    model.add_relu()

    # filter to channel number
    model.add_conv2d(nunits, mapsize=1, stride=1, stddev_factor=2.)
    model.add_relu()

    # output
    model.add_conv2d(channels, mapsize=1, stride=1, stddev_factor=1.)
    model.add_sigmoid()

    # get variables
    new_vars  = tf.global_variables()#tf.all_variables() , all_variables() are deprecated
    gene_vars = list(set(new_vars) - set(old_vars))

    # select subset of layers
    output_layers = [model.outputs[0]] + model.outputs[1:-1][::layer_output_skip] + [model.outputs[-1]]

    return model.get_output(), gene_vars, output_layers

"""

'''
def _generator_model_with_scale(sess, features, labels, masks, channels, layer_output_skip=5,
                                num_dc_layers=0):
    
    channels = 2
    #image_size = tf.shape(features)
    mapsize = 3
    res_units  = [128,128]  #, 128, 128, 128, 128] #[64, 32, 16]#[256, 128, 96]
    scale_changes = [0,0,0,0,0,0,0,0]
    print('use resnet without pooling:', res_units)
    old_vars = tf.global_variables()#tf.all_variables() , all_variables() are deprecated

    # See Arxiv 1603.05027
    model = Model('GEN', features)

    # loop different levels
    for ru in range(len(res_units)-1):
        nunits  = res_units[ru]

        for j in range(2):  #(2)
            model.add_residual_block(nunits, mapsize=mapsize)

        # Spatial upscale (see http://distill.pub/2016/deconv-checkerboard/)
        # and transposed convolution
        if scale_changes[ru]>0:
            model.add_upscale()

        model.add_batch_norm()
        model.add_relu()
        model.add_conv2d_transpose(nunits, mapsize=mapsize, stride=1, stddev_factor=1.)


    # Finalization a la "all convolutional net"
    nunits = res_units[-1]
    model.add_conv2d(nunits, mapsize=mapsize, stride=1, stddev_factor=2.)
    # Worse: model.add_batch_norm()
    model.add_relu()

    model.add_conv2d(nunits, mapsize=1, stride=1, stddev_factor=2.)
    # Worse: model.add_batch_norm()
    model.add_relu()

    # Last layer is sigmoid with no batch normalization
    model.add_conv2d(channels, mapsize=1, stride=1, stddev_factor=1.)
    #model.add_sigmoid()

    output = model.outputs[-1]

    
    #hard data consistency
    masks_comp = 1.0 - masks
    correct_kspace = downsample(labels, masks) + downsample(output, masks_comp)
    correct_image = upsample(correct_kspace, masks)
    model.add_layer(correct_image)
    
    
    
    #inexact data consistency. can be repeated using a for loop
    output_neg = -1*output
    model.add_layer(output_neg)
    model.add_sum(labels)
    model.add_downsample(masks)
    model.add_upsample(masks)
    model.add_scale(stddev_factor=1.)
    model.add_sum(output)
       

    ##inexact affine projection
    #ww = 0.01
    #for kk in range(10):
          #output = output + ww*upsample(downsample(labels-output, masks), masks)

    #output = model.output[-1]
    #model.add_layer(output)
    
    new_vars  = tf.global_variables()    #tf.all_variables() , all_variables() are deprecated
    gene_vars = list(set(new_vars) - set(old_vars))

    # select subset of layers
    output_layers = model.outputs[0] # [model.outputs[0]] + model.outputs[1:-1][::layer_output_skip] + [model.outputs[-1]]

    return model.get_output(), gene_vars, output_layers

'''
'''
def _generator_model_with_scale_modf(sess, features, labels, masks, channels, layer_output_skip=5,
                                num_dc_layers=0):

    channels = 3
    #image_size = tf.shape(features)
    mapsize = 3
    res_units  = [128] #[64, 32, 16]#[256, 128, 96]
    scale_changes = [0,0]
    print('use resnet without pooling:', res_units)
    old_vars = tf.global_variables()#tf.all_variables() , all_variables() are deprecated

    # See Arxiv 1603.05027
    model = Model('GEN', features)

    #bypass connection
    bypass = model.get_output()

    # loop different levels
    for ru in range(len(res_units)):
        nunits  = res_units[ru]

        for j in range(1):  #(2)
            model.add_residual_block(nunits, mapsize=mapsize)

        # Spatial upscale (see http://distill.pub/2016/deconv-checkerboard/)
        # and transposed convolution
        if scale_changes[ru]>0:
            model.add_upscale()

        #model.add_batch_norm()
        #model.add_relu()
        #model.add_conv2d_transpose(nunits, mapsize=mapsize, stride=1, stddev_factor=1.)


    ## Finalization a la "all convolutional net"
    #nunits = res_units[-1]
    #model.add_conv2d(nunits, mapsize=mapsize, stride=1, stddev_factor=2.)
    ## Worse: model.add_batch_norm()
    #model.add_relu()

    #model.add_conv2d(nunits, mapsize=1, stride=1, stddev_factor=2.)
    ## Worse: model.add_batch_norm()
    #model.add_relu()

    # Last layer is sigmoid with no batch normalization
    model.add_conv2d(channels, mapsize=1, stride=1, stddev_factor=1.)
    model.add_sum(bypass)  #new:bypass connection
    model.add_sigmoid()

    output_bdc = model.outputs[-1]   #output brfore dc 
    output_1 = output_bdc
    print('size', output_bdc.get_shape())
    
    
    
    # data consistency, a gradient step
    K=4
    output = 0*output_1 + upsample(downsample(labels-output_1, K), K)
    #print('size_up', output.get_shape())
    model.add_layer(output)
    model.add_conv2d(channels, mapsize=1, stride=1, stddev_factor=1.)
    #model.add_scale(channels, mapsize=1, stride=1, stddev_factor=1.)
    model.add_sum(output_1)
    output_brelu = model.outputs[-1]
    model.add_relu()
    output_relu = model.outputs[-1]


    new_vars  = tf.global_variables()    #tf.all_variables() , all_variables() are deprecated
    gene_vars = list(set(new_vars) - set(old_vars))

    # select subset of layers
    output_layers = [model.outputs[0]] + [output_bdc] + [output_brelu] + [output_relu]          #  model.outputs[0]] + model.outputs[1:-1][::layer_output_skip] + [model.outputs[-1]]

    return model.get_output(), gene_vars, output_layers
'''


'''
def _generator_model_singlelayer_cnn(sess, features, labels, masks, channels, layer_output_skip=5,
                                num_dc_layers=0):

    channels = 3
    #image_size = tf.shape(features)
    mapsize = 8
    res_units  = [3] #[64, 32, 16]#[256, 128, 96]
    scale_changes = [0,0]
    print('use resnet without pooling:', res_units)
    old_vars = tf.global_variables()    #tf.all_variables() , all_variables() are deprecated

    model = Model('GEN', features)

    #CNN with a single layer
    nunits = res_units[-1]
    model.add_conv2d(nunits, mapsize=mapsize, stride=1, stddev_factor=2.) #no bias!!!??
    model.add_batch_norm()


    ##two more conv layers
    #model.add_conv2d(nunits, mapsize=mapsize, stride=1, stddev_factor=2.)
    #model.add_batch_norm()
    #model.add_conv2d(nunits, mapsize=mapsize, stride=1, stddev_factor=2.)
    #model.add_batch_norm()


    output_brelu = model.outputs[-1]
    model.add_relu()
    output_relu = model.outputs[-1]
    print('shape_output_relu', output_relu.get_shape())


    # data consistency, a gradient step
    K=1
    output = 0*output_relu + upsample(downsample(labels-output_relu, K), K)

    model.add_layer(output)
    #model.add_conv2d(channels, mapsize=1, stride=1, stddev_factor=1.)
    model.add_scale(stddev_factor=1.)

    model.add_sum(output_relu)

    output_dc = model.outputs[-1]


    new_vars  = tf.global_variables()    #tf.all_variables() , all_variables() are deprecated
    gene_vars = list(set(new_vars) - set(old_vars))

    # select subset of layers
    output_layers = [model.outputs[0]] + [output_brelu] + [output_relu] +  [output_dc]      #  model.outputs[0]] + model.outputs[1:-1][::layer_output_skip] + [model.outputs[-1]]

    return model.get_output(), gene_vars, output_layers
'''


'''
def _generator_model_singlelayer_cnn(sess, features, labels, masks, channels, layer_output_skip=5,
                                num_dc_layers=0):

    channels = 2
    #image_size = tf.shape(features)
    mapsize = 3
    #nunits  = 2
    old_vars = tf.global_variables()

    model = Model('GEN', features)

    #state variable; 

    #approximate data consistency
    labels_hat = 0*features + upsample(downsample(labels-features, masks), masks)
    print('labels_hat', labels_hat.get_shape())
    print('features', features.get_shape())
    model.add_layer(labels_hat)
    model.add_scale(stddev_factor=1.)
    model.add_sum(features)
    state_var = model.outputs[-1]
    
    

    ##hard data consistency
    #masks_comp = 1 - masks
    #correct_kspace = downsample(labels, masks) + downsample(features, masks_comp)
    #correct_image = upsample(correct_kspace, masks)
    #model.add_layer(correct_image)
    #xxx = 0*features
    #model.add_sum(xxx)
    #xx = model.outputs[-1]
    #print('xx_shape', xx.get_shape())
    


    ##CNN with a single layer
    #model.add_conv2d(16, mapsize=mapsize, stride=1, stddev_factor=2.)
    #model.add_batch_norm()   #???
    #model.add_conv2d(16, mapsize=mapsize, stride=1, stddev_factor=2.)
    #model.add_batch_norm()   #???
    #model.add_conv2d(2, mapsize=mapsize, stride=1, stddev_factor=2.)
    ##model.add_batch_norm()   #???
    ##model.add_conv2d(nunits, mapsize=mapsize, stride=1, stddev_factor=2.)
    ##model.add_batch_norm()   #???
    ##model.add_conv2d(nunits, mapsize=mapsize, stride=1, stddev_factor=2.)
    ##model.add_batch_norm()   #???
    ##model.add_conv2d(nunits, mapsize=mapsize, stride=1, stddev_factor=2.)
    #output_brelu = model.outputs[-1]
    ##ReLU activation
    #model.add_relu()
    #output_relu = model.outputs[-1]
    #output_layers = [features] + [state_var] + [output_brelu] + [output_relu]
    

    #CNN with a single layer - modified and skip connection
    num_units = 64
    bypass = model.outputs[-1]
    model.add_conv2d(num_units, mapsize=mapsize, stride=1, stddev_factor=2.)
    model.add_batch_norm()
    output_brelu_layer_1 = model.outputs[-1]
    model.add_relu()
    output_layer_1 = model.outputs[-1]
    zz = tf.cast(tf.zeros(tf.shape(output_layer_1), tf.int32), tf.float32)
    print('shape_zz', zz.get_shape())
    mask_1 = tf.cast(tf.greater(output_layer_1, zz), tf.float32)
    model.add_conv2d(2, mapsize=mapsize, stride=1, stddev_factor=2.)
    model.add_sum(bypass)
    output_last = model.outputs[-1]
    #gene_masks = [mask_1]
    output_layers = [features] + [output_brelu_layer_1] + [output_layer_1] + [mask_1] + [output_last]
    

    
    #CNN with two layers
    model.add_conv2d(16, mapsize=mapsize, stride=1, stddev_factor=2.)
    model.add_batch_norm()
    output_brelu_layer_1 = model.outputs[-1]
    model.add_relu()
    output_layer_1 = model.outputs[-1]
    mask_1 = tf.cast(tf.greater(output_layer_1, zeros), tf.float32)
    model.add_conv2d(16, mapsize=mapsize, stride=1, stddev_factor=2.)
    model.add_batch_norm()
    output_brelu_layer_2 = model.outputs[-1]
    model.add_relu()
    output_layer_2 = model.outputs[-1]
    mask_2 = tf.cast(tf.greater(output_layer_2, zeros), tf.float32)
    model.add_conv2d(2, mapsize=mapsize, stride=1, stddev_factor=2.)
    output_last = model.outputs[-1]
    #gene_masks = [mask_1] + [mask_2]
    output_layers = [features] + [output_brelu_layer_1] + [output_layer_1] + [mask_1] + [output_brelu_layer_2] + [output_layer_2] + [mask_2] + [output_last]
    
    
    #fully connected (dense) layer
    shape_input = tf.shape(state_var)
    vec_input = tf.reshape(state_var, [shape_input[0],-1])
    model.add_layer(vec_input)
    model.add_dense(nunits, stddev_factor=1.0)
    vec_output = model.outputs[-1]
    output = tf.reshape(vec_output, shape_input)
    model.add_layer(output)
    

    new_vars  = tf.global_variables() 
    gene_vars = list(set(new_vars) - set(old_vars))

    return model.get_output(), gene_vars, output_layers
'''


def create_model(sess, features, labels, masks, architecture='resnet'):
    # sess: TF sesson
    # features: input, for SR/CS it is the input image
    # labels: output, for SR/CS it is the groundtruth image
    # architecture: aec for encode-decoder, resnet for upside down 
    # Generator
    rows      = int(features.get_shape()[1])
    cols      = int(features.get_shape()[2])
    channels  = int(features.get_shape()[3])

    #print('channels', features.get_shape())

    gene_minput = tf.placeholder(tf.float32, shape=[FLAGS.batch_size, rows, cols, channels])
    label_minput = tf.placeholder(tf.float32, shape=[FLAGS.batch_size, rows, cols, channels])

    architecture = 'aec' #only deal with the autoencoder


    # TBD: Is there a better way to instance the generator?
    if architecture == 'aec':
        function_generator = lambda x,y,z,w: _generator_encoder_decoder(x,y,z,w)
    elif architecture == 'pool':
        function_generator = lambda x,y,z,w: _generator_model_with_pool(x,y,z,w)
    elif architecture.startswith('var'):
        num_dc_layers = 1
        if architecture!='var':
            try:
                num_dc_layers = int(architecture.split('var')[-1])
            except:
                pass
        function_generator = lambda x,y,z,m,w: _generator_model_with_scale(x,y,z,m,w,
                                                layer_output_skip=7, num_dc_layers=num_dc_layers)
    else:
        function_generator = lambda x,y,z,m,w: _generator_model_with_scale(x,y,z,m,w,
                                                layer_output_skip=7, num_dc_layers=0)


    #gene_var_list = []
    gene_layers_list = []
    gene_mlayers_list = []
    gene_output_list = []
    gene_moutput_list = []
    mask_list = []
    mask_list_0 = []
    eta = []

    kappa = []
    nmse = []

    with tf.variable_scope('gene_layer') as scope:

        gene_output = features
        gene_moutput = gene_minput

        for i in range(FLAGS.num_iteration):

             #train
             gene_output, gene_var_list, gene_layers = function_generator(sess, gene_output, labels, masks)
             gene_layers_list.append(gene_layers)
             gene_output_list.append(gene_output)

             scope.reuse_variables()
             #test
             gene_moutput, _ , gene_mlayers = function_generator(sess, gene_moutput, label_minput, masks)
             gene_mlayers_list.append(gene_mlayers)
             gene_moutput_list.append(gene_moutput)
             #mask_list.append(gene_mlayers[3])

             scope.reuse_variables()
             #evaluate at the groun-truth solution
             gene_moutput_0, _ , gene_mlayers_0 = function_generator(sess, label_minput, label_minput, masks)
             #mask_list_0 = gene_mlayers_0[3]

             #nmse_t = tf.square(tf.divide(tf.norm(gene_moutput - labels), tf.norm(labels)))
             #nmse.append(nmse_t)
             #kappa_t = tf.divide(tf.norm(gene_moutput - labels), tf.norm(gene_mlayers[0] - labels))
             #kappa.append(kappa_t)

             ##convergence rate kappa_t = ||x_{t+1}-x_*||/||x_t-x_*||
             #kappa_t = tf.divide(tf.norm(gene_mlayers[4] - labels), tf.norm(gene_mlayers[0] - labels))
             #nmse_t = tf.divide(tf.norm(gene_mlayers[4] - labels), tf.norm(labels))
             #kappa.append(kappa_t)
             #nmse.append(nmse_t)
             

    #eta = tf.zeros([4,4]) #eta_1 + eta_2
                    

    #Discriminator with real data
    gene_output_complex = tf.complex(gene_output[:,:,:,0], gene_output[:,:,:,1])
    gene_output_real = tf.abs(gene_output_complex)
    gene_output_real = tf.reshape(gene_output_real, [FLAGS.batch_size, rows, cols, 1])   #gene_output

    labels_complex = tf.complex(labels[:,:,:,0], labels[:,:,:,1])
    labels_real = tf.abs(labels_complex)
    labels_real = tf.reshape(labels_real, [FLAGS.batch_size, rows, cols, 1])   #gene_output

    disc_real_input = tf.identity(labels_real, name='disc_real_input')


    # TBD: Is there a better way to instance the discriminator?
    with tf.variable_scope('disc') as scope:
        print('hybrid_disc', FLAGS.hybrid_disc)
        disc_real_output, disc_var_list, disc_layers = \
                _discriminator_model(sess, features, disc_real_input, hybrid_disc=FLAGS.hybrid_disc)

        scope.reuse_variables()

            
        disc_fake_output, _, _ = _discriminator_model(sess, features, gene_output_real, hybrid_disc=FLAGS.hybrid_disc)

    return [gene_minput, label_minput, gene_moutput, gene_moutput_list,
            gene_output, gene_output_list, gene_var_list, gene_layers_list, gene_mlayers_list, mask_list, mask_list_0,
            disc_real_output, disc_fake_output, disc_var_list, disc_layers, eta, nmse, kappa]   


# SSIM
def keras_var(x, axis=None, keepdims=False):
    """Variance of a tensor, alongside the specified axis.
    # Arguments
        x: A tensor or variable.
        axis: An integer, the axis to compute the variance.
        keepdims: A boolean, whether to keep the dimensions or not.
            If `keepdims` is `False`, the rank of the tensor is reduced
            by 1. If `keepdims` is `True`,
            the reduced dimension is retained with length 1.
    # Returns
        A tensor with the variance of elements of `x`.
    """
    # axis = _normalize_axis(axis, ndim(x))
    if x.dtype.base_dtype == tf.bool:
        x = tf.cast(x, floatx())
    m = tf.reduce_mean(x, reduction_indices=axis, keep_dims=True)
    devs_squared = tf.square(x - m)
    return tf.reduce_mean(devs_squared,
                          reduction_indices=axis,
                          keep_dims=keepdims)


def keras_std(x, axis=None, keepdims=False):
    """Standard deviation of a tensor, alongside the specified axis.
    # Arguments
        x: A tensor or variable.
        axis: An integer, the axis to compute the standard deviation.
        keepdims: A boolean, whether to keep the dimensions or not.
            If `keepdims` is `False`, the rank of the tensor is reduced
            by 1. If `keepdims` is `True`,
            the reduced dimension is retained with length 1.
    # Returns
        A tensor with the standard deviation of elements of `x`.
    """
    return tf.sqrt(keras_var(x, axis=axis, keepdims=keepdims))


def keras_mean(x, axis=None, keepdims=False):
    """Mean of a tensor, alongside the specified axis.
    # Arguments
        x: A tensor or variable.
        axis: A list of integer. Axes to compute the mean.
        keepdims: A boolean, whether to keep the dimensions or not.
            If `keepdims` is `False`, the rank of the tensor is reduced
            by 1 for each entry in `axis`. If `keep_dims` is `True`,
            the reduced dimensions are retained with length 1.
    # Returns
        A tensor with the mean of elements of `x`.
    """
    # axis = _normalize_axis(axis, ndim(x))
    if x.dtype.base_dtype == tf.bool:
        x = tf.cast(x, floatx())
    return tf.reduce_mean(x, reduction_indices=axis, keep_dims=keepdims)

def loss_DSSIS_tf11(y_true, y_pred, patch_size=5, batch_size=-1):
    # get batch size
    if batch_size<0:
        batch_size = int(y_true.get_shape()[0])
    else:
        y_true = tf.reshape(y_true, [batch_size] + get_shape(y_pred)[1:])
        y_pred = tf.reshape(y_pred, [batch_size] + get_shape(y_pred)[1:])
    # batch, x, y, channel
    # y_true = tf.transpose(y_true, [0, 2, 3, 1])
    # y_pred = tf.transpose(y_pred, [0, 2, 3, 1])
    patches_true = tf.extract_image_patches(y_true, [1, patch_size, patch_size, 1], [1, 2, 2, 1], [1, 1, 1, 1], "SAME")
    patches_pred = tf.extract_image_patches(y_pred, [1, patch_size, patch_size, 1], [1, 2, 2, 1], [1, 1, 1, 1], "SAME")
    #print(patches_true, patches_pred)
    u_true = keras_mean(patches_true, axis=3)
    u_pred = keras_mean(patches_pred, axis=3)
    #print(u_true, u_pred)
    var_true = keras_var(patches_true, axis=3)
    var_pred = keras_var(patches_pred, axis=3)
    std_true = tf.sqrt(var_true)
    std_pred = tf.sqrt(var_pred)
    #print(std_true, std_pred)
    c1 = 0.01 ** 2
    c2 = 0.03 ** 2
    ssim = (2 * u_true * u_pred + c1) * (2 * std_pred * std_true + c2)
    denom = (u_true ** 2 + u_pred ** 2 + c1) * (var_pred + var_true + c2)
    ssim /= denom
    #print(ssim)
    # ssim = tf.select(tf.is_nan(ssim), K.zeros_like(ssim), ssim)
    return tf.reduce_mean(((1.0 - ssim) / 2), name='ssim_loss')

def create_generator_loss(disc_output, gene_output, gene_output_list, features, labels, masks):
    
    # Cross entropy GAN cost
    cross_entropy = tf.nn.sigmoid_cross_entropy_with_logits(logits=disc_output, labels=tf.ones_like(disc_output))
    gene_ce_loss  = tf.reduce_mean(cross_entropy, name='gene_ce_loss')

    # LS GAN cost
    ls_loss = tf.square(disc_output - tf.ones_like(disc_output))
    gene_ls_loss  = tf.reduce_mean(ls_loss, name='gene_ls_loss')

    # I.e. does the result look like the feature?
    # K = int(gene_output.get_shape()[1])//int(features.get_shape()[1])
    # assert K == 2 or K == 4 or K == 8    
    # downscaled = _downscale(gene_output, K)


    # soft data-consistency loss
    #image_size = [128, 128]
    #K=2
    gene_dc_loss = 0
    for j in range(FLAGS.num_iteration):
    	gene_dc_loss =  gene_dc_loss + tf.cast(tf.reduce_mean(tf.square(tf.abs(downsample(labels - gene_output_list[j], masks))), name='gene_dc_loss'), tf.float32)

    gene_dc_norm = tf.cast(tf.reduce_mean(tf.square(tf.abs(downsample(labels, masks))), name='gene_dc_norm'), tf.float32)
    gene_dc_loss = gene_dc_loss / (gene_dc_norm * FLAGS.num_iteration)


    
    #generator MSE loss summed up over different copies
    gene_l2_loss = 0
    gene_l1_loss = 0
    for j in range(FLAGS.num_iteration):

        gene_l2_loss =  gene_l2_loss + tf.cast(tf.reduce_mean(tf.square(tf.abs(gene_output_list[j] - labels)), name='gene_l2_loss'), tf.float32)
        gene_l1_loss =  gene_l2_loss + tf.cast(tf.reduce_mean(tf.abs(gene_output_list[j] - labels), name='gene_l2_loss'), tf.float32)
    
     
    '''
    # mse loss
    gene_l1_loss  = tf.cast(tf.reduce_mean(tf.abs(gene_output - labels), name='gene_l1_loss'), tf.float32)
    gene_l2_loss  = tf.cast(tf.reduce_mean(tf.square(tf.abs(gene_output - labels)), name='gene_l2_loss'), tf.float32)
    '''

    # mse loss
    gene_mse_loss = tf.add(FLAGS.gene_l1l2_factor * gene_l1_loss, 
                        (1.0 - FLAGS.gene_l1l2_factor) * gene_l2_loss, name='gene_mse_loss')

    #ssim loss
    gene_ssim_loss = loss_DSSIS_tf11(labels, gene_output)
    gene_mixmse_loss = tf.add(FLAGS.gene_ssim_factor * gene_ssim_loss, 
                            (1.0 - FLAGS.gene_ssim_factor) * gene_mse_loss, name='gene_mixmse_loss')
    
    # generator fool descriminator loss: gan LS or log loss
    gene_fool_loss = tf.add(FLAGS.gene_ls_factor * gene_ls_loss,
                           FLAGS.gene_log_factor * gene_ce_loss, name='gene_fool_loss')

    # non-mse loss = fool-loss + data consisntency loss
    gene_non_mse_l2     = gene_fool_loss  #tf.add((1.0 - FLAGS.gene_dc_factor) * gene_fool_loss,
                           #FLAGS.gene_dc_factor * gene_dc_loss, name='gene_nonmse_l2')
       
    gene_mse_factor  = tf.placeholder(dtype=tf.float32, name='gene_mse_factor')

    #total loss = fool-loss + data consistency loss + mse forward-passing loss
    #gene_loss     = tf.add((1.0 - FLAGS.gene_mse_factor) * gene_non_mse_l2, 
                            #FLAGS.gene_mse_factor * gene_mixmse_loss, name='gene_loss')

    #gene_mse_factor as a parameter
    #gene_loss  = tf.add((1.0 - gene_mse_factor) * gene_non_mse_l2,
                                  #gene_mse_factor * gene_mixmse_loss, name='gene_loss')

    gene_loss_pre  = tf.add((1.0 - gene_mse_factor) * gene_non_mse_l2,
                                  gene_mse_factor * gene_mixmse_loss, name='gene_loss')

    gene_loss = tf.add(FLAGS.gene_dc_factor * gene_dc_loss,
                                  (1.0 - FLAGS.gene_dc_factor) * gene_loss_pre, name='gene_loss')

    #list of loss
    list_gene_lose = [gene_mixmse_loss, gene_mse_loss, gene_l2_loss, gene_l1_loss, gene_ssim_loss, # regression loss
                        gene_dc_loss, gene_fool_loss, gene_non_mse_l2, gene_loss]


    # log to tensorboard
    #tf.summary.scalar('gene_non_mse_loss', gene_non_mse_l2)
    tf.summary.scalar('gene_fool_loss', gene_non_mse_l2)
    tf.summary.scalar('gene_dc_loss', gene_dc_loss)
    #tf.summary.scalar('gene_ls_loss', gene_ls_loss)
    tf.summary.scalar('gene_L1_loss', gene_mixmse_loss)


    return gene_loss, gene_dc_loss, gene_fool_loss, gene_mse_loss, list_gene_lose, gene_mse_factor
    

def create_discriminator_loss(disc_real_output, disc_fake_output):
    # I.e. did we correctly identify the input as real or not?
    # cross_entropy_real = tf.nn.sigmoid_cross_entropy_with_logits(logits=disc_real_output, labels=tf.ones_like(disc_real_output))
    # disc_real_loss     = tf.reduce_mean(cross_entropy_real, name='disc_real_loss')
    
    # cross_entropy_fake = tf.nn.sigmoid_cross_entropy_with_logits(logits=disc_fake_output, labels=tf.zeros_like(disc_fake_output))
    # disc_fake_loss     = tf.reduce_mean(cross_entropy_fake, name='disc_fake_loss')

    # ls loss
    ls_loss_real = tf.square(disc_real_output - tf.ones_like(disc_real_output))
    disc_real_loss = tf.reduce_mean(ls_loss_real, name='disc_real_loss')

    ls_loss_fake = tf.square(disc_fake_output)
    disc_fake_loss = tf.reduce_mean(ls_loss_fake, name='disc_fake_loss')

        # log to tensorboard
    tf.summary.scalar('disc_real_loss',disc_real_loss)
    tf.summary.scalar('disc_fake_loss',disc_fake_loss)


    return disc_real_loss, disc_fake_loss

def create_optimizers(gene_loss, gene_var_list,
                      disc_loss, disc_var_list):    
    # TBD: Does this global step variable need to be manually incremented? I think so.
    global_step    = tf.Variable(0, dtype=tf.int64,   trainable=False, name='global_step')
    learning_rate  = tf.placeholder(dtype=tf.float32, name='learning_rate')
    
    gene_opti = tf.train.AdamOptimizer(learning_rate=learning_rate,
                                       beta1=FLAGS.learning_beta1,
                                       name='gene_optimizer')
    disc_opti = tf.train.AdamOptimizer(learning_rate=learning_rate,
                                       beta1=FLAGS.learning_beta1,
                                       name='disc_optimizer')
    
    ##gradient clipping 
    ##method 1. the right method
    grads_and_vars = gene_opti.compute_gradients(gene_loss)  #, gene_var_list)
    #[print('grad', grad) for grad, var in grads_and_vars]
    capped_grads_and_vars = [(tf.clip_by_value(gv[0], -1000000000., 1000000000.), gv[1]) for gv in grads_and_vars]
    gene_minimize = gene_opti.apply_gradients(capped_grads_and_vars)
    



    ##method 2
    #print(gene_opti)
    #print('****************************************')
    #tvars = tf.trainable_variables()
    #grads, _ = tf.clip_by_global_norm(tf.gradients(gene_loss, tvars), 1)
    #gene_opti = gene_opti.apply_gradients(zip(grads, tvars))
    #print(gene_opti) 
     

    #gene_minimize = gene_opti.minimize(gene_loss, var_list=gene_var_list, name='gene_loss_minimize', global_step=global_step)
    
    disc_minimize = disc_opti.minimize(disc_loss, var_list=disc_var_list, name='disc_loss_minimize', global_step=global_step)
    
    return (global_step, learning_rate, gene_minimize, disc_minimize)



