import logging
import random

import numpy as np
import tensorflow as tf

import energy_py
from energy_py.common.utils import save_args, parse_ini
from energy_py.common.logging import make_logger

from energy_py.common.experiments import Runner, save_env_info, make_paths


def experiment(
        agent_config,
        env_config,
        total_steps,
        paths,
        seed=None):
    """
    Run an experiment of multiple episodes

    args
        agent_config (dict)
        env_config (dict)
        total_steps (int)
        paths (dict)
        seed (int)

    Episodes are run until total_steps are reached.
    Agent and environment are created from config dictionaries
    """
    logger = make_logger(paths, 'master')

    tf.reset_default_graph()
    with tf.Session() as sess:

        env = energy_py.make_env(**env_config)
        save_args(env_config, path=paths['env_args'])
        logger.info('random seed is {}'.format(seed))

        if seed:
            seed = int(seed)
            env.seed(seed)
            random.seed(seed)
            tf.set_random_seed(seed)
            np.random.seed(seed)

        #  add stuff into the agent config dict
        agent_config['env'] = env
        agent_config['sess'] = sess
        agent_config['act_path'] = paths['tb_act']
        agent_config['learn_path'] = paths['tb_learn']

        #  init agent and save args
        agent = energy_py.make_agent(**agent_config)
        if hasattr(agent, 'acting_writer'):
            agent.acting_writer.add_graph(sess.graph)
        save_args(agent_config, path=paths['agent_args'])

        #  runner helps to manage our experiment
        runner = Runner(sess, paths, total_steps)

        #  outer while loop runs through multiple episodes
        step, episode = 0, 0
        while step < int(total_steps):
            episode += 1
            done = False
            observation = env.reset()

            #  inner while loop runs through a single episode
            while not done:
                step += 1
                #  select an action
                action = agent.act(observation)
                #  take one step through the environment
                next_observation, reward, done, info = env.step(action)
                #  store the experience
                agent.remember(observation, action, reward,
                               next_observation, done)
                runner.record_step(reward)
                #  moving to the next time step
                observation = next_observation

                #  fill the memory up halfway before we learn
                #  TODO the agent should decide what to do internally here
                if step > int(agent.memory.size * 0.5):
                    train_info = agent.learn()

            runner.record_episode(env_info=info)

            save_env_info(
                env,
                info,
                len(runner.episode_rewards),
                paths['env_histories']
            )


def run_config_expt(expt_name, run_name, expt_path):
    """ runs an experiment from a config file """
    paths = make_paths(expt_path, run_name=run_name)

    agent_config = parse_ini(paths['run_configs'], run_name)
    env_config = parse_ini(paths['common_config'], 'ENV')

    experiment(
        agent_config=agent_config,
        env_config=env_config,
        total_steps=agent_config['total_steps'],
        paths=paths,
        seed=agent_config.pop('seed')
    )
