from __future__ import absolute_import, division, print_function

from torch.autograd import Variable, grad
from torch.distributions.transforms import identity_transform


def unconstrained_velocity_verlet(z, r, potential_fn, step_size, num_steps):
    """
    Second order symplectic integrator that uses the velocity verlet algorithm.

    :param dict z: dictionary of sample site names and their current values
        (type ``torch.autograd.Variable``).
    :param dict r: dictionary of sample site names and corresponding momenta
        (type ``torch.autograd.Variable``).
    :param callable potential_fn: function that returns potential energy given z
        for each sample site. The negative gradient of the function with respect
        to ``z`` determines the rate of change of the corresponding sites'
        momenta ``r``.
    :param float step_size: step size for each time step iteration.
    :param int num_steps: number of discrete time steps over which to integrate.
    :return tuple (z_next, r_next): final position and momenta, having same types as (z, r).
    """
    z_next = {key: val.data.clone() for key, val in z.items()}
    r_next = {key: val.data.clone() for key, val in r.items()}
    grads = _grad(potential_fn, z_next)

    for _ in range(num_steps):
        for site_name in z_next:
            # r(n+1/2)
            r_next[site_name] = r_next[site_name] + 0.5 * step_size * (-grads[site_name])
            # z(n+1)
            z_next[site_name] = z_next[site_name] + step_size * r_next[site_name]
        grads = _grad(potential_fn, z_next)
        for site_name in r_next:
            # r(n+1)
            r_next[site_name] = r_next[site_name] + 0.5 * step_size * (-grads[site_name])
    z_next = {key: Variable(val) for key, val in z_next.items()}
    r_next = {key: Variable(val) for key, val in r_next.items()}
    return z_next, r_next


def _grad(potential_fn, z):
    z = {k: Variable(v, requires_grad=True) for k, v in z.items()}
    z_keys, z_nodes = zip(*z.items())
    grads = grad(potential_fn(z), z_nodes)
    grads = [v.data for v in grads]
    return dict(zip(z_keys, grads))


def velocity_verlet(z, r, potential_fn, step_size, num_steps, transforms={}):
    u = {transforms.get(name, identity_transform)(z_name) for name, z_name in z.items()}

    def unconstrained_potential_fn(u):
        z = {transforms.get(name, identity_transform).inv(u_name) for name, u_name in u.items()}
        result = potential_fn(z)
        for site_name, transform in transforms.items():
            result += transform.log_abs_det_jacobian(u[name], z[name]).sum()
        return result

    u_next, r_next = unconstrained_velocity_verlet(u, r, unconstrained_potential_fn, step_size, num_steps)
    z_next = {transforms.get(name, identity_transform).inv(u_name) for name, u_name in u_next.items()}
    return z_next, r_next
