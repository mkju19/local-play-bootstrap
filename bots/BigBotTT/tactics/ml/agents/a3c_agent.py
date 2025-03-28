import logging
import os
import pickle
import gzip
import random
from datetime import datetime
from typing import List, Union, Callable, Tuple

import numpy as np
import tensorflow as tf
from tensorflow.python import keras
from tensorflow.python.keras import layers

import jsonpickle
from filelock.filelock import FileLock
from tactics.ml.agents import BaseMLAgent
from numpy.core.multiarray import ndarray

from tactics.ml.agents.memory import Memory, MemoryData

logger = logging.getLogger(__name__)

SAVE_DIR = "./data/"


def record(episode, episode_reward, worker_idx, global_ep_reward, total_loss, num_steps, log_print):
    """Helper function to store score and print statistics.

    Arguments:
      episode: Current episode
      episode_reward: Reward accumulated over the current episode
      worker_idx: Which thread (worker)
      global_ep_reward: The moving average of the global reward
      total_loss: The total loss accumualted over the current episode
      num_steps: The number of steps the episode took to complete
    """
    if global_ep_reward == 0:
        global_ep_reward = episode_reward
    else:
        global_ep_reward = global_ep_reward * 0.99 + episode_reward * 0.01
    text = (
        f"Episode: {episode} | "
        f"Moving Average Reward: {int(global_ep_reward)} | "
        f"Episode Reward: {int(episode_reward)} | "
        f"Loss: {int(total_loss / float(num_steps) * 1000) / 1000} | "
        f"Steps: {num_steps} | "
        f"Worker: {worker_idx}"
    )
    log_print(text)
    return global_ep_reward


#
# class ActorCriticModel(keras.Model):
#     def __init__(self, state_size, action_size):
#         super(ActorCriticModel, self).__init__()
#         self.state_size = state_size
#         self.action_size = action_size
#         self.dense1 = layers.Dense(100, activation="relu")
#         self.policy_logits = layers.Dense(action_size)
#         self.dense2 = layers.Dense(100, activation="relu")
#         self.values = layers.Dense(1)
#
#     def call(self, inputs):
#         # Forward pass
#         x = self.dense1(inputs)
#         logits = self.policy_logits(x)
#         v1 = self.dense2(inputs)
#         values = self.values(v1)
#         return logits, values


class ActorCriticModel(keras.Model):
    def __init__(self, state_size, action_size, hidden_size: int = 200):
        super(ActorCriticModel, self).__init__()
        self.state_size = state_size
        self.action_size = action_size
        self.actor_dense = layers.Dense(hidden_size, activation="relu")
        self.policy_logits = layers.Dense(action_size)
        # self.actor_dense2 = layers.Dense(hidden_size, activation="relu")
        self.critic_dense = layers.Dense(hidden_size, activation="relu")
        self.values = layers.Dense(1)

    def call(self, inputs):
        # Decision making
        x = self.actor_dense(inputs)
        # x = self.dense2(mid_x)
        logits = self.policy_logits(x)

        # values for converging model
        v1 = self.critic_dense(inputs)
        # v1 = self.dense3(x)
        values = self.values(v1)
        return logits, values


class A3CAgent(BaseMLAgent):
    # Set up global variables across different threads
    episode = 0
    # Moving average reward
    global_moving_average_reward = 0
    best_score = 0

    def __init__(
        self,
        env_name: str,
        state_size,
        action_size,
        learning_rate=0.003,
        gamma=0.995,
        start_temperature=100,
        temperature_episodes=10000,
        log_print: Callable[[str], None] = print,
        mask: List[Tuple[int, float]] = None,
    ):
        """
        Create standard learning A3C agent.

        @param env_name: this is used for naming the model so that different games have different models
        @param state_size: Size of the input observation array. Integer support only for now
        @param action_size: Size of possible output.  Integer support only for now
        @param learning_rate: Learning rate. Something between 0.01 and 0.0001 should be fine
        @param gamma: Should define how meaningful early game actions are to late game rewards
        @param start_temperature: Increases randomness for the softmax action selection probability function
        @param temperature_episodes: How long to use temperature to increase randomness
        @param log_print: custom function for writing logs, defaults to "print"
        """
        self.create_optimizer = lambda: tf.keras.optimizers.Adam(learning_rate=learning_rate)
        # self.create_optimizer = lambda: tf.keras.optimizers.RMSprop(learning_rate=learning_rate)
        super().__init__(state_size, action_size)

        self.mask: List[Tuple[int, float]] = mask
        self.temperature_episodes = temperature_episodes
        self.start_temperature = start_temperature
        self.learning_rate = learning_rate
        self.print = log_print
        tf.enable_eager_execution()  # Required for some numpy code.
        # tf.compat.v1.enable_eager_execution()
        assert env_name is not str

        self.MODEL_NAME = "model_" + env_name
        self.MODEL_FILE_NAME = f"{self.MODEL_NAME}.h5"
        self.MODEL_FILE_PATH = os.path.join(SAVE_DIR, self.MODEL_FILE_NAME)
        self.OPTIMIZER_FILE_NAME = f"{self.MODEL_NAME}.opt.npy"  # pgz
        self.OPTIMIZER_FILE_PATH = os.path.join(SAVE_DIR, self.OPTIMIZER_FILE_NAME)
        self.MODEL_FILE_LOCK_PATH = os.path.join(SAVE_DIR, f"{self.MODEL_FILE_NAME}.lock")
        self.GLOBAL_RECORDS_FILE_NAME = f"{self.MODEL_NAME}.records.json"
        self.GLOBAL_RECORDS_FILE_PATH = os.path.join(SAVE_DIR, self.GLOBAL_RECORDS_FILE_NAME)
        self.LOG_FILE_NAME = f"{self.MODEL_NAME}.log"
        self.LOG_FILE_PATH = os.path.join(SAVE_DIR, self.LOG_FILE_NAME)

        self.MASTER_MODEL_NAME = "model_" + env_name.split(".")[0] + ".master"
        self.MASTER_MODEL_FILE_NAME = f"{self.MASTER_MODEL_NAME}.h5"
        self.MASTER_MODEL_FILE_PATH = os.path.join(SAVE_DIR, self.MASTER_MODEL_FILE_NAME)
        self.MASTER_MODEL_FILE_LOCK_PATH = os.path.join(SAVE_DIR, f"{self.MASTER_MODEL_FILE_NAME}.lock")
        self.MASTER_GLOBAL_RECORDS_FILE_NAME = f"{self.MASTER_MODEL_NAME}.records.json"
        self.MASTER_GLOBAL_RECORDS_FILE_PATH = os.path.join(SAVE_DIR, self.MASTER_GLOBAL_RECORDS_FILE_NAME)

        if not os.path.exists(SAVE_DIR):
            os.makedirs(SAVE_DIR)

        with FileLock(self.MODEL_FILE_LOCK_PATH):
            if not os.path.isfile(self.MODEL_FILE_PATH):
                global_model = ActorCriticModel(self.state_size, self.action_size)
                global_model(tf.convert_to_tensor(np.random.random((1, self.state_size)), dtype=tf.float32))
                # global_model(tf.convert_to_tensor(np.zeros((1, self.state_size)), dtype=tf.float32))
                global_model.save_weights(self.MODEL_FILE_PATH)

            if not os.path.isfile(self.OPTIMIZER_FILE_PATH):
                # Create saved optimizer
                optimizer = self.create_optimizer()
                grad_vars = global_model.trainable_weights
                zero_grads = [tf.zeros_like(w) for w in grad_vars]
                # Apply gradients which don't do nothing with Adam
                optimizer.apply_gradients(zip(zero_grads, grad_vars))

                np.save(self.OPTIMIZER_FILE_PATH, optimizer.get_weights())

                # with gzip.GzipFile(self.OPTIMIZER_FILE_PATH, "wb") as f:
                #     pickle.dump(tf.keras.optimizers.Adam(learning_rate=learning_rate), f)

            if not os.path.isfile(self.GLOBAL_RECORDS_FILE_PATH):
                # Create saved global records
                with open(self.GLOBAL_RECORDS_FILE_PATH, "w") as f:
                    global_records = {
                        "global_episode": 1,
                        "global_moving_average_reward": 0,
                    }
                    frozen = jsonpickle.encode(global_records)
                    f.write(frozen)
            else:
                with open(self.GLOBAL_RECORDS_FILE_PATH, "r") as f:
                    text = f.read()
                    global_records = jsonpickle.decode(text)

            self.local_model = ActorCriticModel(self.state_size, self.action_size)
            self.local_model(tf.convert_to_tensor(np.random.random((1, self.state_size)), dtype=tf.float32))
            # self.local_model(tf.convert_to_tensor(np.zeros((1, self.state_size)), dtype=tf.float32))
            self.local_model.load_weights(self.MODEL_FILE_PATH)
        self.episode = global_records["global_episode"]
        self.mem = Memory()

        self.prev_action = None
        self.prev_state = None

        self.ep_reward = 0

        self.ep_steps = 0
        self.time_count = 0
        self.total_step = 0
        self.gamma = gamma

        self.ep_loss = 0
        self.save_learning_data = True  # Saves memory to json file
        self.merge_master = False  # Merges learned gradients to master file
        self.checkpoint_interval = 100  # Store checkpoint of the model after amount of episodes. Set to 0 for never

    def evaluate_prev_action_reward(self, reward: float):
        if self.prev_action is not None:
            # TODO: rename reward to score or something to reflect that it's the current state value
            self.ep_reward = reward
            self.mem.store(self.prev_state, self.prev_action, reward)

    def choose_action(self, state: ndarray, reward: float) -> int:
        """Choose and return the next action.
        """
        self.evaluate_prev_action_reward(reward)

        logits, values = self.local_model(tf.convert_to_tensor(state[None, :], dtype=tf.float32))

        if self.episode < self.temperature_episodes:
            # https://en.wikipedia.org/wiki/Softmax_function#Reinforcement_learning
            # Increases randomness
            logits /= (
                1 + self.start_temperature * (self.temperature_episodes - self.episode) / self.temperature_episodes
            )
        probs = tf.nn.softmax(logits).numpy()

        if self.mask and len(self.mask) > 0:
            for mask in self.mask:
                probs[0][mask[0]] = mask[1]
            probs /= probs.sum()  # Normalization

        self.prev_action = np.random.choice(self.action_size, p=probs[0])
        self.prev_state = state

        self.ep_steps += 1

        return self.prev_action

    def on_end(self, state: List[Union[float, int]], reward: float):
        self.evaluate_prev_action_reward(reward)
        grads = self.calc_gradients(reward, state)
        self.save_memory()
        self.save_global_model(grads)
        self.reset()

    def save_memory(self):
        if not self.save_learning_data:
            return
        self.print("Saving memory")
        time = datetime.now().strftime("%Y-%m-%d %H_%M_%S")
        randomizer = random.randint(0, 999999)
        file_name = f"data_{time}_{randomizer}"
        self.mem.save(os.path.join(SAVE_DIR, "learning"), file_name + "_" + self.MODEL_NAME)
        self.print("Memory saved")

    def save_global_model(self, grads):
        self.print("Saving global model")

        global_model = ActorCriticModel(self.state_size, self.action_size)
        global_model(tf.convert_to_tensor(np.random.random((1, self.state_size)), dtype=tf.float32))

        with FileLock(self.MODEL_FILE_LOCK_PATH):
            global_model.load_weights(self.MODEL_FILE_PATH)

            optimizer: tf.keras.optimizers.Optimizer
            # rebuild optimizer
            optimizer = self.create_optimizer()
            grad_vars = global_model.trainable_weights
            zero_grads = [tf.zeros_like(w) for w in grad_vars]
            # Apply gradients which don't do nothing with Adam
            optimizer.apply_gradients(zip(zero_grads, grad_vars))
            # Get saved weights
            opt_weights = np.load(self.OPTIMIZER_FILE_PATH, allow_pickle=True)
            # Set the weights of the optimizer
            optimizer.set_weights(opt_weights)

            # with open(self.OPTIMIZER_FILE_PATH, "rb") as f:
            # with gzip.open(self.OPTIMIZER_FILE_PATH, "rb") as f:
            #     optimizer = pickle.load(f)

            global_records: dict
            with open(self.GLOBAL_RECORDS_FILE_PATH, "r") as f:
                text = f.read()
                global_records = jsonpickle.decode(text)

            # work with the file as it is now locked

            # Push local gradients to global model
            optimizer.apply_gradients(zip(grads, global_model.trainable_weights))
            # Update local model with new weights
            self.local_model.set_weights(global_model.get_weights())

            # if done:  # done and print information
            # Worker.global_moving_average_reward = \
            #     record(Worker.global_episode, self.ep_reward, 1, #self.worker_idx,
            #            Worker.global_moving_average_reward, self.result_queue,
            #            self.ep_loss, ep_steps)
            global_records["global_moving_average_reward"] = record(
                global_records["global_episode"],
                self.ep_reward,
                1,  # self.worker_idx,
                global_records["global_moving_average_reward"],
                self.ep_loss,
                self.ep_steps,
                log_print=self.print,
            )
            # We must use a lock to save our model and to print to prevent data races.
            # if self.ep_reward > Worker.best_score:
            # if self.ep_reward > A3CAgent.best_score:
            #     A3CAgent.best_score = self.ep_reward
            #     print("New best score: ".format(A3CAgent.best_score))

            global_model.save_weights(self.MODEL_FILE_PATH)

            # Save optimizer weights.
            np.save(self.OPTIMIZER_FILE_PATH, optimizer.get_weights())

            # with gzip.GzipFile(self.OPTIMIZER_FILE_PATH, "wb") as f:
            #     pickle.dump(optimizer, f)

            episode = global_records["global_episode"]
            if self.checkpoint_interval > 0 and episode % self.checkpoint_interval == 0:
                # ensure path
                path = os.path.join(SAVE_DIR, f"e{episode}")
                from pathlib import Path

                Path(path).mkdir(parents=True, exist_ok=True)
                # Save backup model
                backup_path = os.path.join(path, self.MODEL_FILE_NAME)
                backup_path_opt = os.path.join(path, self.OPTIMIZER_FILE_NAME)
                backup_path_record = os.path.join(path, self.GLOBAL_RECORDS_FILE_NAME)

                global_model.save_weights(backup_path)

                # Save optimizer weights.
                np.save(backup_path_opt, optimizer.get_weights())
                # with gzip.GzipFile(backup_path_opt, "wb") as f:
                #     # with open(backup_path_opt, "wb") as f:
                #     pickle.dump(optimizer, f)

                with open(backup_path_record, "w") as f:
                    frozen = jsonpickle.encode(global_records)
                    f.write(frozen)

            # Worker.global_episode += 1
            global_records["global_episode"] += 1

            # Save global records
            with open(self.GLOBAL_RECORDS_FILE_PATH, "w") as f:
                frozen = jsonpickle.encode(global_records)
                f.write(frozen)

        self.print("Global model saved")

        self.merge_master_model(grads, optimizer)

    def calc_gradients(self, reward, state):
        # Calculate gradient wrt to local model. We do so by tracking the
        # variables involved in computing the loss by using tf.GradientTape
        with tf.GradientTape() as tape:
            total_loss = self.compute_loss(True, state, self.mem, self.gamma)
            self.ep_loss += total_loss
            # Calculate local gradients
            grads = tape.gradient(total_loss, self.local_model.trainable_weights)
        return grads

    def reset(self):
        self.mem.clear()
        self.time_count = 0
        self.prev_action = None
        self.prev_state = None
        self.ep_reward = 0
        self.ep_steps = 0
        self.time_count = 0
        self.total_step = 0
        self.ep_loss = 0

    def merge_master_model(self, grads, optimizer):
        if not self.merge_master:
            return

        self.print("Saving master model")

        with FileLock(self.MASTER_MODEL_FILE_LOCK_PATH):
            if not os.path.isfile(self.MASTER_GLOBAL_RECORDS_FILE_PATH):
                master_global_records = {
                    "global_episode": 0,
                    "global_moving_average_reward": 0,
                }
            else:
                with open(self.MASTER_GLOBAL_RECORDS_FILE_PATH, "r") as f:
                    text = f.read()
                    master_global_records = jsonpickle.decode(text)

            master_global_records["global_episode"] = master_global_records["global_episode"] + 1

            master_global_model = ActorCriticModel(self.state_size, self.action_size)
            master_global_model(tf.convert_to_tensor(np.random.random((1, self.state_size)), dtype=tf.float32))

            if os.path.isfile(self.MASTER_MODEL_FILE_PATH):
                master_global_model.load_weights(self.MASTER_MODEL_FILE_PATH)

            optimizer.apply_gradients(zip(grads, master_global_model.trainable_weights))

            # We must use a lock to save our model and to print to prevent data races.

            master_global_model.save_weights(self.MASTER_MODEL_FILE_PATH)

            # Save global records
            with open(self.MASTER_GLOBAL_RECORDS_FILE_PATH, "w") as f:
                frozen = jsonpickle.encode(master_global_records)
                f.write(frozen)

        self.print("Master model saved")

    def compute_loss(self, done, new_state, memory_obj: Memory, gamma):
        memory: MemoryData = memory_obj.data

        if done:
            reward_sum = 0.0  # terminal
        else:
            reward_sum = self.local_model(tf.convert_to_tensor(new_state[None, :], dtype=tf.float32))[-1].numpy()[0]

        # Get discounted rewards (calc difference)
        discounted_rewards = []
        for i in range(0, len(memory.rewards)):
            # Iterate in reverse to calculate reward sum
            score = memory.rewards[-1 - i]
            # Our reward number actually represents score, not reward
            # Get diff between current score and previous score to get reward

            if i >= len(memory.rewards) - 1:
                # First action, set reward to 0
                reward = 0
            else:
                reward = score - memory.rewards[-2 - i]
            # Reward sum is the expected value of the action
            reward_sum = reward + gamma * reward_sum
            discounted_rewards.append(reward_sum)

        # Get discounted rewards
        # discounted_rewards = []
        # for reward in memory.rewards[::-1]:  # reverse buffer r
        #     reward_sum = reward + gamma * reward_sum
        #     discounted_rewards.append(reward_sum)

        # Because we iterated in reverse, reverse to make it align with states
        discounted_rewards.reverse()

        logits, critic_values = self.local_model(tf.convert_to_tensor(np.vstack(memory.states), dtype=tf.float32))
        # Get our advantages
        advantage = tf.convert_to_tensor(np.array(discounted_rewards)[:, None], dtype=tf.float32) - critic_values
        # Value loss
        critic_loss = advantage ** 2

        # Calculate our policy loss (v2)
        # actions_one_hot = tf.one_hot(memory.actions, self.action_size, dtype=tf.float32)
        #
        # policy = tf.nn.softmax(logits)
        # entropy = tf.reduce_sum(policy * tf.log(policy + 1e-20), axis=1)
        #
        # policy_loss = tf.nn.softmax_cross_entropy_with_logits_v2(labels=actions_one_hot, logits=logits)
        # policy_loss *= tf.stop_gradient(advantage)
        # policy_loss -= 0.01 * entropy
        # total_loss = tf.reduce_mean((0.5 * value_loss + policy_loss))

        # Calculate our policy loss (Old)
        policy = tf.nn.softmax(logits)
        entropy = tf.nn.softmax_cross_entropy_with_logits_v2(labels=policy, logits=logits)

        policy_loss = tf.nn.sparse_softmax_cross_entropy_with_logits(labels=memory.actions, logits=logits)
        policy_loss *= tf.stop_gradient(advantage)
        policy_loss -= 0.01 * entropy
        total_loss = tf.reduce_mean((0.5 * critic_loss + policy_loss))

        print(f"[RL-total_loss] {total_loss}")
        # self.print(f'[RL-value_loss] {value_loss} ')
        # self.print(f'[RL-policy] {policy}')
        self.print(f"[RL-entropy] {tf.reduce_mean(entropy)}")
        self.print(f"[RL-policy_loss] {tf.reduce_mean(policy_loss)}")
        self.print(f"[RL-total_loss] {total_loss}")

        return total_loss
