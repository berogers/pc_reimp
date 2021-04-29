# Implementation of r&b 1999 predictive coding model with MNIST data.

import numpy as np
from matplotlib import pyplot as plt
# from kbutil.plotting import pylab_pretty_plot
from learning import *
from functools import partial
import math

# activation functions
def linear_trans(U_dot_r):
    """ Though intended to operate on some U.dot(r), will take any numerical
    argument x and return the tuple (f(x), F(x)). Linear transformation. """
    f = U_dot_r
    F = np.eye(len(f))
    return (f, F)



def tanh_trans(U_dot_r):
    """ Though intended to operate on some U.dot(r), will take any numerical
    argument x and return the tuple (f(x), F(x)). Tanh transformation. """
    f = np.tanh(U_dot_r)
    F = np.diag(1 - f.flatten()**2)
    return (f, F)



# r, U prior functions
def gauss_prior(r_or_U, alph_or_lam):
    """ Takes an argument pair of either r & alpha, or U & lambda, and returns
    a tuple of (g(r), g'(r)), or (h(U), h'(U)), respectively. Gaussian prior. """
    g_or_h = alph_or_lam * np.square(r_or_U).sum()
    gprime_or_hprime = 2 * alph_or_lam * r_or_U
    return (g_or_h, gprime_or_hprime)



def kurt_prior(r_or_U, alph_or_lam):
    """ Takes an argument pair of either r & alpha, or U & lambda, and returns
    a tuple of (g(r), g'(r)), or (h(U), h'(U)), respectively. Sparse kurtotic prior. """
    g_or_h = alph_or_lam * np.log(1 + np.square(r_or_U)).sum()
    gprime_or_hprime = 2 * alph_or_lam * r_or_U / (1 + np.square(r_or_U))
    return (g_or_h, gprime_or_hprime)



# softmax function
def softmax(r):
    return np.exp(r) / np.exp(r).sum()



class PredictiveCodingClassifier:
    def __init__(self, parameters):

        self.p = parameters

        # possible choices for transformations, priors
        self.unit_act = {'linear':linear_trans,'tanh':tanh_trans}
        self.prior_dict = {'gaussian':gauss_prior, 'kurtotic':kurt_prior}

        # # NOTE: may use this functionality later
        # # possible classification methods
        # self.class_cost_dict = {'C1':class_c1, 'C2':class_c2}

        # all the representations (including the image r[0] which is not trained)
        self.r = {}

        # synaptic weights controlling reconstruction in the network
        self.U = {}

        # priors and transforms
        self.f = self.unit_act[self.p.unit_act]
        # how to call f(x): self.f(self.U.dot(self.r))[0]
        # how to call F(x): self.f(self.U.dot(self.r))[1]

        self.g = self.prior_dict[self.p.r_prior]
        # how to call g(r): self.g(self.r,self.p.alpha)[0]
        # how to call g'(r): self.g(self.r,self.p.alpha)[1]

        self.h = self.prior_dict[self.p.U_prior]
        # how to call h(U): self.h(self.U,self.p.lam)[0]
        # how to call h'(U): self.h(self.U,self.p.lam)[1]


        # # classification method
        # self.class_cost = self.class_cost_dict[self.p.classification]
        # # if C1, how to call C1: C = C - self.class_cost(self.r[n], label)
        # # if C2, how to call C2: C = self.class_cost(self.r[n], self.U_o, label) + \
        # # (self.h(self.U_o,self.p.lam[n-1])[0])[0,0]

        # learning rate functions (can't figure out how to dispatch this)
        lr_r = list(self.p.k_r_sched.keys())[0]
        if lr_r == 'constant':
            self.k_r_lr = partial(constant_lr,initial=self.p.k_r_sched['constant']['initial'])
        elif lr_r == 'step':
            self.k_r_lr = partial(step_decay_lr,initial=self.p.k_r_sched['step']['initial'],drop_every=self.p.k_r_sched['step']['drop_every'],drop_factor=self.p.k_r_sched['step']['drop_factor'])
        elif lr_r == 'poly':
            self.k_r_lr = partial(polynomial_decay_lr,initial=self.p.k_r_sched['poly']['initial'],max_epochs=self.p.k_r_sched['poly']['max_epochs'],poly_power=self.p.k_r_sched['poly']['poly_power'])

        lr_U = list(self.p.k_U_sched.keys())[0]
        if lr_U == 'constant':
            self.k_U_lr = partial(constant_lr,initial=self.p.k_U_sched['constant']['initial'])
        elif lr_U == 'step':
            self.k_U_lr = partial(step_decay_lr,initial=self.p.k_U_sched['step']['initial'],drop_every=self.p.k_U_sched['step']['drop_every'],drop_factor=self.p.k_U_sched['step']['drop_factor'])
        elif lr_U == 'poly':
            self.k_U_lr = partial(polynomial_decay_lr,initial=self.p.k_U_sched['poly']['initial'],max_epochs=self.p.k_U_sched['poly']['max_epochs'],poly_power=self.p.k_U_sched['poly']['poly_power'])

        lr_o = list(self.p.k_o_sched.keys())[0]
        if lr_o == 'constant':
            self.k_o_lr = partial(constant_lr,initial=self.p.k_o_sched['constant']['initial'])
        elif lr_o == 'step':
            self.k_o_lr = partial(step_decay_lr,initial=self.p.k_o_sched['step']['initial'],drop_every=self.p.k_o_sched['step']['drop_every'],drop_factor=self.p.k_o_sched['step']['drop_factor'])
        elif lr_o == 'poly':
            self.k_o_lr = partial(polynomial_decay_lr,initial=self.p.k_o_sched['poly']['initial'],max_epochs=self.p.k_o_sched['poly']['max_epochs'],poly_power=self.p.k_o_sched['poly']['poly_power'])


        #make initial learning rate self.variables for plotting.py
        self.lr_r = list(list(self.p.k_r_sched.values())[0].values())[0]
        self.lr_U = list(list(self.p.k_U_sched.values())[0].values())[0]
        self.lr_o = list(list(self.p.k_o_sched.values())[0].values())[0]

        # total number of layers (Input, r1, r2... rn, Output)
        self.n_layers = len(self.p.hidden_sizes) + 2
        # number of non-image layers (r1, r2... rn, Output)
        self.n_non_input_layers = len(self.p.hidden_sizes) + 1
        # number of hidden layers (r1, r2... rn)
        self.n_hidden_layers = len(self.p.hidden_sizes)

        # initialize appropriate r's and U's
        # N.B - MAY NEED TO SET THE FOLLOWING PROPERLY USING PRIORS AT SOME POINT

        # initialize image input layer of size (input_size,)
        self.r[0] = np.random.randn(self.p.input_size,1)

        print('\n')
        print("*** Predictive Coding Classifier ***")
        print('\n')
        print("*** Layer shapes ***")
        print('\n')
        print("r[0] shape is " + str(np.shape(self.r[0])))
        print('\n')

        # dict to contain number of neural network parameters per layer comprising the model
        self.nn_parameters_dict = {}

        # initialize r's and U's for hidden layers
        # calculate number of network parameters per layer
        for i in range(1,self.n_non_input_layers):
            self.r[i] = np.random.randn(self.p.hidden_sizes[i-1],1)
            self.U[i] = np.random.randn(len(self.r[i-1]),len(self.r[i]))
            ri = "r_{}".format(i)
            Ui = "U_{}".format(i)
            self.nn_parameters_dict[ri] = len(self.r[i])
            self.nn_parameters_dict[Ui] = np.shape(self.U[i])[0]*np.shape(self.U[i])[1]

            print("r[{}] shape is ".format(i) + str(np.shape(self.r[i])))
            print('\n')
            print("U[{}] shape is ".format(i) + str(np.shape(self.U[i])))
            print('\n')

        print("len(self.r): " + str(len(self.r)))
        print('\n')

        # initialize "output" layer
        self.o = np.random.randn(self.p.output_size,1)
        # and final set of weights to the output
        self.U_o = np.random.randn(self.p.output_size,self.p.hidden_sizes[-1])

        print("o shape is " + str(np.shape(self.o)))
        print('\n')
        print("U_o shape is " + str(np.shape(self.U_o)))
        print('\n')

        # calculate total number of network parameters comprising the model (hidden layers only)
        self.n_model_parameters = sum(self.nn_parameters_dict.values())

        print("*** Network Parameters ***")
        print('\n')
        print("number of neural network parameters per hidden layer: " + str(self.nn_parameters_dict))
        print('\n')
        print("total number of hidden layer parameters: {}".format(self.n_model_parameters))
        print('\n')

        return



    def rep_cost(self):
        '''
        Uses current r/U states to compute the least squares portion of the error
        (concerned with accurate reconstruction of the input).
        '''
        E = 0
        # LSQ cost
        for i in range(0,len(self.r)-1):
            v = (self.r[i] - self.f(self.U[i+1].dot(self.r[i+1]))[0])
            E = E + ((1 / self.p.sigma_sq[i+1]) * v.T.dot(v))[0,0]
        # priors on r[1],...,r[n]; U[1],...,U[n]
        for i in range(1,len(self.r)):
            E = E + (self.h(self.U[i],self.p.lam[i])[0] + self.g(np.squeeze(self.r[i]),self.p.alpha[i])[0])
        return E



    def class_cost_1(self,label):
        """ Calculates the classification portion of the cost function output of a training
        image using classification method C1. """
        n = self.n_hidden_layers
        C1 = -1*label[None,:].dot(np.log(softmax(self.r[n])))[0,0]
        return C1



    def class_cost_2(self,label):
        """ Calculates the classification portion of the cost function output of a training
        image using classification method C2, uninclusive of the prior term. """
        n = self.n_hidden_layers
        C2 = -1*label[None,:].dot(np.log(softmax((self.U_o.dot(self.r[n])))))[0,0]
        return C2

    def prediction_error(self,layer_number):
        """ Calculates the normed prediction error of a layer (in [i,n]), i.e. the difference between a
        the layer's image prediction ("r^td") and the image representation from the layer below ("r"). """
        pe = math.sqrt((self.r[layer_number-1]-self.f(self.U[layer_number].dot(self.r[layer_number]))[0]).T\
        .dot(self.r[layer_number-1]-self.f(self.U[layer_number].dot(self.r[layer_number]))[0]))
        return pe



    def train(self,X,Y):
        '''
        X: matrix of input patterns (N_patterns x input_size)
        Y: matrix of output/target patterns (N_patterns x output_size)

        I'm pretty sure the R&B model basically requires a batch size of 1, since
        we have to fit the r's to each individual image and they are ephemeral.
        '''

        # average cost per epoch during training; just representation terms
        self.E_avg_per_epoch = []
        # average cost per epoch during training; just classification term
        self.C_avg_per_epoch = []
        # accuracy per epoch during training
        self.acc_per_epoch = []

        # number of hidden layers
        n = self.n_hidden_layers

        print("*** Training ***")
        print('\n')

        # loop through training image dataset num_epochs times
        for epoch in range(0,self.p.num_epochs):
            # shuffle order of training set input image / output vector pairs each epoch
            N_permuted_indices = np.random.permutation(X.shape[0])
            X_shuffled = X[N_permuted_indices]
            Y_shuffled = Y[N_permuted_indices]

            # print("y_shuffled shape is: " + '\n' + str(Y_shuffled.shape))

            # number of training images
            num_images = X_shuffled.shape[0]

            # we compute average cost per epoch (batch size = 1); separate classification
            #   and representation costs so we can compare OOM sizes
            E = 0
            C = 0

            # accuracy per epoch: how many images are correctly guessed per epoch
            num_correct = 0

            # set learning rates at the start of each epoch
            k_r = self.k_r_lr(epoch)
            k_U = self.k_U_lr(epoch)
            k_o = self.k_o_lr(epoch)

            # print("*** train() function values and layers ***")
            # print("Number of training images is {}".format(num_images) + '\n')

            print("epoch {}".format(epoch+1))
            # XXX DEBUG
            # print(k_r,k_U,k_o)
            # print('\n')

            # loop through training images
            for image in range(0, num_images):

                # print("image {}".format(image+1))
                # print('\n')


                # copy first image into r[0]
                self.r[0] = X_shuffled[image,:][:,None]

                # initialize new r's
                for layer in range(1,self.n_non_input_layers):
                    # self state per layer
                    self.r[layer] = np.random.randn(self.p.hidden_sizes[layer-1],1)


                # initialize "output" layer o (for classification method 2 (C2))
                self.o = np.random.randn(self.p.output_size,1)
                # and final set of weights U_o to the output (C2)
                self.U_o = np.random.randn(self.p.output_size,self.p.hidden_sizes[-1])
                # designate label vector
                label = Y_shuffled[image,:]


                # loop through intermediate layers (will fail if number of hidden layers is 1)
                # r,U updates written symmetrically for all layers including output
                for i in range(1,n):


                    # NOTE: self.p.k_r learning rate
                    # r[i] update
                    self.r[i] = self.r[i] + ((k_r / self.p.sigma_sq[i]) \
                    * self.U[i].T.dot(self.f(self.U[i].dot(self.r[i]))[1].dot(self.r[i-1] - self.f(self.U[i].dot(self.r[i]))[0])))/784 \
                    + ((k_r / self.p.sigma_sq[i+1]) * (self.f(self.U[i+1].dot(self.r[i+1]))[0] - self.r[i]))/32 \
                    - (k_r / 2) * self.g(self.r[i],self.p.alpha[i])[1]


                    # U[i] update
                    self.U[i] = self.U[i] + ((k_U / self.p.sigma_sq[i]) \
                    * (self.f(self.U[i].dot(self.r[i]))[1].dot(self.r[i-1] - self.f(self.U[i].dot(self.r[i]))[0])).dot(self.r[i].T))/784 \
                    - (k_U / 2) * self.h(self.U[i],self.p.lam[i])[1]


                # """ r(n) update (C1) """
                # self.r[n] = self.r[n] + ((k_r / self.p.sigma_sq[n]) \
                # * self.U[n].T.dot(self.f(self.U[n].dot(self.r[n]))[1].dot(self.r[n-1] - self.f(self.U[n].dot(self.r[n]))[0])))/32 \
                # - (k_r / 2) * self.g(self.r[n],self.p.alpha[n])[1] \
                # # classification term
                # + (k_o / 2) * (label[:,None] - softmax(self.r[n]))

                """ r(n) update (C2) """
                self.r[n] = self.r[n] + ((k_r / self.p.sigma_sq[n]) \
                * self.U[n].T.dot(self.f(self.U[n].dot(self.r[n]))[1].dot(self.r[n-1] - self.f(self.U[n].dot(self.r[n]))[0])))/32 \
                - (k_r / 2) * self.g(self.r[n],self.p.alpha[n])[1] \
                # classification term
                + (k_r / 2) * (self.U_o.T.dot(label[:,None]) - self.U_o.T.dot(softmax(self.U_o.dot(self.r[n]))))


                # U[n] update (C1, C2) (identical to U[i], except index numbers)
                self.U[n] = self.U[n] + ((k_U / self.p.sigma_sq[n]) \
                * (self.f(self.U[n].dot(self.r[n]))[1].dot(self.r[n-1] - self.f(self.U[n].dot(self.r[n]))[0])).dot(self.r[n].T))/32 \
                - (k_U / 2) * self.h(self.U[n],self.p.lam[n])[1]


                """ U_o update (C2) """
                self.o = np.exp(self.U_o.dot(self.r[n]))
                self.U_o = self.U_o + label[:,None].dot(self.r[n].T) - len(label)*softmax((self.U_o.dot(self.r[n])).dot(self.r[n].T))



                # Loss function E

                E = self.rep_cost()


                # Classification cost function C

                # if not classifying, default classification type is "NC"
                self.class_type = 'NC'

                # """ Classifying using C1 """
                # C = self.class_cost_1(label)
                # E = E + C
                # self.class_type = 'C1'


                """ Classifying using C2 """
                C = self.class_cost_2(label)
                E = E + C
                self.class_type = 'C2'


                # Classification Accuracy

                # if index of the max value in final representation vector
                # = index of the 1 in associated one hot label vector
                # then the model classified the image correctly
                # and add 1 to num_correct


                # """ C1 method """
                # if np.argmax(softmax(self.r[n])) == np.argmax(label[:,None]):
                #     num_correct += 1


                """ C2 method """
                c2_output = self.U_o.dot(self.r[n])

                if np.argmax(softmax(c2_output)) == np.argmax(label[:,None]):
                    num_correct += 1


            # store average costs and accuracy per epoch
            E_avg_per_epoch = E/num_images
            C_avg_per_epoch = C/num_images
            acc_per_epoch = round((num_correct/num_images)*100)

            self.E_avg_per_epoch.append(E_avg_per_epoch)
            self.C_avg_per_epoch.append(C_avg_per_epoch)
            self.acc_per_epoch.append(acc_per_epoch)


        return



    def predict(self,X,X_name,prior_type,classif_type,num_updates):
        '''
        Given one or more inputs, produce one or more outputs.
        '''


        # number of hidden layers
        n = self.n_hidden_layers

        print("*** Predicting ***")
        print('\n')


        # representation costs for zeroth and nth layers
        self.pe_1 = []
        self.pe_2 = []

        # accuracy per epoch: how many images are correctly guessed per epoch
        num_correct = 0

        # set learning rate for r
        k_r = 0.05


        # loop through testing images
        for image in range(0, 1):

            # copy first image into r[0]

            # print(X[image].shape)
            self.r[0] = X[image][:,None]

            # print(X[image].shape)
            # print(X[image][:,None].shape)
            # print(self.r[0].shape)
            # print("fUr shape")
            # print((self.f(self.U[1].dot(self.r[1]))[0]).shape)


            # initialize new r's
            for layer in range(1,self.n_non_input_layers):
                # self state per layer
                self.r[layer] = np.random.randn(self.p.hidden_sizes[layer-1],1)
                # print('rlayer')
                # print(self.r[layer].shape)



            for update in range(0,num_updates):

                # magnitude (normed) prediction errors each "layer" (i.e. error between r0,r1, and r1,r2)

                pe_1 = self.prediction_error(1)
                pe_2 = self.prediction_error(2)

                self.pe_1.append(pe_1)
                self.pe_2.append(pe_2)

                # loop through intermediate layers (will fail if number of hidden layers is 1)
                # r,U updates written symmetrically for all layers including output
                for i in range(1,n):


                    # r[i] update
                    self.r[i] = self.r[i] + (k_r / self.p.sigma_sq[i]) \
                    * self.U[i].T.dot(self.f(self.U[i].dot(self.r[i]))[1].dot(self.r[i-1] - self.f(self.U[i].dot(self.r[i]))[0])) \
                    + (k_r / self.p.sigma_sq[i+1]) * (self.f(self.U[i+1].dot(self.r[i+1]))[0] - self.r[i]) \
                    - (k_r / 2) * self.g(self.r[i],self.p.alpha[i])[1]


                self.r[n] = self.r[n] + (k_r / self.p.sigma_sq[n]) \
                * self.U[n].T.dot(self.f(self.U[n].dot(self.r[n]))[1].dot(self.r[n-1] - self.f(self.U[n].dot(self.r[n]))[0])) \
                - (k_r / 2) * self.g(self.r[n],self.p.alpha[n])[1]


            # for plotting: move out of predict() later

            pe_1_first = round(self.pe_1[0],1)
            pe_1_last = round(self.pe_1[-1],1)
            pe_2_first = round(self.pe_2[0],1)
            pe_2_last = round(self.pe_2[-1],1)

            num_updates = range(1, num_updates+1)

            fig, ax = plt.subplots(1)
            fig.suptitle("{}  {}  {}  {}  ".format(self.p.unit_act,classif_type,prior_type,X_name)+"lr_r={} ".format(self.lr_r)+'\n'\
            +'pe_1_first={} '.format(pe_1_first)+'pe_1_last={} '.format(pe_1_last)\
            + 'pe_2_first={} '.format(pe_2_first) + 'pe_2_last={} '.format(pe_2_last))

            # lime_green:'#3cb44b'
            # magenta_red:'#e6194b'
            # sky_blue:'#4363d8'
            # light_orange:'#f58231'
            # bright_purple:'#911eb4'
            # turquoise:'#46f0f0'
            # magenta_pink:'#f032e6'
            # neon_yellow_green:'#bcf60c'
            # pink_skin:'#fabebe'
            # dark_lakefoam_green:'#008080'
            # powder_pink:'#e6beff'
            # popcorn_yellow:'#fffac8'
            # carmel_brown:'#9a6324'
            # dark_chocolate:'#800000'
            # keylime_pie:'#aaffc3'
            # camo_green:'#808000'
            # cooked_salmon:'#ffd8b1'
            # navy_blue:'#000075'
            # dark_grey:'#808080'
            # white:'#ffffff'
            # black:'#000000'
            # gold_yellow:'#ffe119'


            # black and navy
            plotE = ax.plot(num_updates, self.pe_1, '#000000', label="pe_1")
            plotE = ax.plot(num_updates, self.pe_2, '#000075', label="pe_2")
            ax.set_ylim(0, 50)
            ax.legend()

            ax.set_xlabel("Update")
            ax.set_ylabel("L1, L2 PE")


            plt.show()

            # return final prediction
            # i.e. r[n]

            self.prediction = self.r[2]

            return

        print("Prediction finished.")
        print('\n')

        return
