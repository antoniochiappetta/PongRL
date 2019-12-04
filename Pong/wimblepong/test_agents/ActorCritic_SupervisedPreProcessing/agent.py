import torch
import matplotlib.pyplot as plt
import numpy as np
import random

from test_agents.ActorCritic_SupervisedPreProcessing.models import Policy
from Pong_NN import PongNN as PNN

class Agent(object):

    def __init__(self):

        self.name = "GIORGIA SSJ"

        # TODO: Actor Critic from positions estimate
        self.train_device = "cpu"
        self.policy = None
        self.optimizer = None
        self.gamma = 0.98
        self.states = []
        self.action_probs = []
        self.entropies = []
        self.rewards = []
        self.values = []
        self.prev_obs = None

        # TODO: Supervised learning policies to estimate positions from raw image
        self.NN_ball_x = PNN()
        self.NN_ball_y = PNN()
        self.NN_my_y = PNN()
        self.NN_opponent_y = PNN()
        self.prev_ball_x = None
        self.prev_ball_y = None

    def get_action(self, observation):

        # TODO: Preprocess frame to reduce dimensionality and emphasize paddles/ball over background
        observation = self._preprocess(observation)

        # TODO: Create observation tensor
        observation = torch.from_numpy(observation).float().to(self.train_device)

        # TODO: Predict state variables
        ball_x = self.NN_ball_x(observation).detach().numpy()[0][0]
        ball_y = self.NN_ball_y(observation).detach().numpy()[0][0]
        my_y = self.NN_my_y(observation).detach().numpy()[0][0]
        opponent_y = self.NN_opponent_y(observation).detach().numpy()[0][0]
        if self.prev_ball_x is None:
            self.prev_ball_x = ball_x
        if self.prev_ball_y is None:
            self.prev_ball_y = ball_y

        # TODO: Create approximated positions from supervised predictions
        positions = np.array([my_y, opponent_y, ball_x, ball_y, self.prev_ball_x, self.prev_ball_y])

        # TODO: Store ball predictions for next observation
        self.prev_ball_x = ball_x
        self.prev_ball_y = ball_y

        # TODO: Create positions tensor
        positions = torch.from_numpy(positions).float().to(self.train_device)

        # TODO: Forward positions through the policy network -> Actor provides policy actions dist, Critic provides state value prediction
        dist, value = self.policy.forward(positions)

        # TODO: Sample action from probability distribution
        action = torch.argmax(dist.probs)

        return action

    def reset(self):
        self.prev_obs = None
        self.prev_ball_x = None
        self.prev_ball_y = None

    def get_name(self):
        return self.name

    def load_model(self):

        # TODO: Actor Critic policy and optimizer weights to evaluate or resume training
        self.policy = Policy(6, 3).to(self.train_device)
        weights = torch.load("model.mdl", map_location=torch.device("cpu"))
        self.policy.load_state_dict(weights, strict=False)
        self.optimizer = torch.optim.RMSprop(self.policy.parameters(), lr=5e-4)
        opt_weights = torch.load("opt_model.mdl", map_location=torch.device("cpu"))
        self.optimizer.load_state_dict(opt_weights)
        self.policy.eval()

        # TODO: Supervised learning policies weights used to preprocess image into positions
        ball_x_weights = torch.load("weights_XNN.mdl", map_location=torch.device("cpu"))
        self.NN_ball_x.load_state_dict(ball_x_weights, strict=False)
        ball_y_weights = torch.load("weights_YNN.mdl", map_location=torch.device("cpu"))
        self.NN_ball_y.load_state_dict(ball_y_weights, strict=False)
        my_y_weights = torch.load("weights_myYNN.mdl", map_location=torch.device("cpu"))
        self.NN_my_y.load_state_dict(my_y_weights, strict=False)
        opponent_y_weights = torch.load("weights_oppYNN.mdl", map_location=torch.device("cpu"))
        self.NN_opponent_y.load_state_dict(opponent_y_weights, strict=False)

    def train(self, env, opponent, resume=False, print_things=True, train_episodes=5000):

        # TODO: Set policy network and optimizer according to environment dimensionalities
        if not resume:
            obs_space_dim = env.observation_space.shape[-1]
            act_space_dim = env.action_space.n
            self.policy = Policy(obs_space_dim, act_space_dim).to(self.train_device)
            self.optimizer = torch.optim.RMSprop(self.policy.parameters(), lr=5e-4)

        self.policy.train()

        # TODO: Set arrays to keep track of rewards and then plot them
        reward_history, timestep_history = [], []
        average_reward_history = []

        # # TODO: Run actual training
        for episode_number in range(train_episodes):
            reward_sum = 0
            timesteps = 0
            done = False
            # Reset the environment and observe the initial state
            self.reset()
            observation, opponent_obs = env.reset()

            # Loop until the episode is over
            while not done:
                # Get action from the agent and store state - action prob - value
                action, action_probabilities = self._get_action_train(observation)

                # Get action from opponent
                opponent_action = opponent.get_action(opponent_obs)

                # Perform the action on the environment, get new state and reward
                (observation, opponent_obs), (reward, opponent_rew), done, info = env.step((action.detach().numpy(), opponent_action))

                # Store action's outcome (so that the agent can improve its policy)
                self._store_outcome(reward)

                # Store total episode reward
                reward_sum += reward
                timesteps += 1

            if print_things:
                print("Episode {} finished. Total reward: {:.3g} ({} timesteps)"
                      .format(episode_number, reward_sum, timesteps))

            # Bookkeeping (mainly for generating plots)
            reward_history.append(reward_sum)
            timestep_history.append(timesteps)
            if episode_number > 100:
                avg = np.mean(reward_history[-100:])
            else:
                avg = np.mean(reward_history)
            average_reward_history.append(avg)

            # MC policy gradient update at the end of the episode
            self._episode_finished(episode_number)

        # Training is finished - plot rewards
        if print_things:
            plt.plot(reward_history)
            plt.plot(average_reward_history)
            plt.legend(["Reward", "100-episode average"])
            plt.title("Reward history")
            plt.show()
            print("Training finished.")

        torch.save(self.policy.state_dict(), "model.mdl")
        torch.save(self.optimizer.state_dict(), "opt_model.mdl")

    def _get_action_train(self, observation):

        # TODO: Preprocess frame to reduce dimensionality and emphasize paddles/ball over background
        processed_observation = self._preprocess(observation)

        # TODO: Create observation tensor
        observation = torch.from_numpy(processed_observation).float().to(self.train_device)

        # TODO: Predict state variables
        ball_x = self.NN_ball_x(observation).detach().numpy()[0][0]
        ball_y = self.NN_ball_y(observation).detach().numpy()[0][0]
        my_y = self.NN_my_y(observation).detach().numpy()[0][0]
        opponent_y = self.NN_opponent_y(observation).detach().numpy()[0][0]
        if self.prev_ball_x is None:
            self.prev_ball_x = ball_x
        if self.prev_ball_y is None:
            self.prev_ball_y = ball_y

        # TODO: Create approximated positions from supervised predictions
        positions = np.array([my_y, opponent_y, ball_x, ball_y, self.prev_ball_x, self.prev_ball_y])

        # TODO: Store ball predictions for next observation
        self.prev_ball_x = ball_x
        self.prev_ball_y = ball_y

        # TODO: Create positions tensor
        positions = torch.from_numpy(positions).float().to(self.train_device)

        # TODO: Forward positions through the policy network -> Actor provides policy actions dist, Critic provides state value prediction
        # dist, value = self.policy.forward(positions)  # Train using images
        dist, value = self.policy.forward(observation)  # Train using states

        # TODO: Sample action from probability distribution
        action = torch.argmax(dist.probs)

        # TODO: Calculate the log probability of the action
        act_log_prob = dist.log_prob(action)

        # TODO: Save state - action prob - value
        self.states.append(observation)
        self.action_probs.append(act_log_prob)
        self.entropies.append(dist.entropy())
        self.values.append(value)

        return action, act_log_prob

    def _episode_finished(self, episode_number):

        # TODO: Stack action_probs, rewards and values arrays
        action_probs = torch.stack(self.action_probs, dim=0) \
                .to(self.train_device).squeeze(-1)
        entropies = torch.stack(self.entropies, dim=0).to(self.train_device).squeeze(-1)
        rewards = torch.stack(self.rewards, dim=0).to(self.train_device).squeeze(-1)
        values = torch.stack(self.values, dim=0).to(self.train_device).squeeze(-1)

        # TODO: Reset values for next episode
        self.states, self.action_probs, self.entropies, self.rewards, self.values = [], [], [], [], []

        # TODO: Compute discounted rewards and normalize
        rewards = self._discount_rewards(rewards, gamma=self.gamma)
        rewards = (rewards - torch.mean(rewards))/torch.std(rewards)

        # TODO: Compute advantages
        advantages = rewards - values

        # TODO: Compute loss
        loss = torch.sum(-action_probs * advantages.detach())
        actor_loss = loss.mean()
        critic_loss = advantages.pow(2).mean()
        entropy_loss = entropies.mean()
        actor_critic_loss = 1.0 * actor_loss + 1.0 * critic_loss + 0.05 * entropy_loss

        # TODO: Compute the gradients of loss w.r.t. network parameters
        actor_critic_loss.backward()

        # TODO: Update network parameters
        self.optimizer.step()
        self.optimizer.zero_grad()

    def _store_outcome(self, reward):
        self.rewards.append(torch.Tensor([reward]))

    def _discount_rewards(self, r, gamma):
        discounted_r = torch.zeros_like(r)
        running_add = 0
        for t in reversed(range(0, r.size(-1))):
            running_add = running_add * gamma + r[t]
            discounted_r[t] = running_add
        return discounted_r

    def _preprocess(self, frame):
        frame = frame[::2, ::2, 0]  # down sample by factor of 2
        frame[frame == 43] = 0  # erase background (background type 1)

        frame[frame != 0] = 1  # everything else (paddles, ball) just set to 1
        return frame.astype(np.float).ravel()
