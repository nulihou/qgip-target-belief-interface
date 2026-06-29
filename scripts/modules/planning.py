import numpy as np

class QuinticPolynomial:
    def __init__(self, xs, vxs, axs, xe, vxe, axe, time):
        """
        Calculates the coefficients of a quintic polynomial given the start and end states.
        x(t) = a0 + a1*t + a2*t^2 + a3*t^3 + a4*t^4 + a5*t^5
        """
        self.a0 = xs
        self.a1 = vxs
        self.a2 = axs / 2.0

        A = np.array([
            [time ** 3, time ** 4, time ** 5],
            [3 * time ** 2, 4 * time ** 3, 5 * time ** 4],
            [6 * time, 12 * time ** 2, 20 * time ** 3]
        ])

        b = np.array([
            xe - self.a0 - self.a1 * time - self.a2 * time ** 2,
            vxe - self.a1 - 2 * self.a2 * time,
            axe - 2 * self.a2
        ])

        try:
            x = np.linalg.solve(A, b)
            self.a3 = x[0]
            self.a4 = x[1]
            self.a5 = x[2]
        except np.linalg.LinAlgError:
            # Fallback if singular (e.g. time=0), though unlikely in usage
            self.a3 = 0
            self.a4 = 0
            self.a5 = 0

    def calc_point(self, t):
        xt = self.a0 + self.a1 * t + self.a2 * t ** 2 + \
             self.a3 * t ** 3 + self.a4 * t ** 4 + self.a5 * t ** 5
        return xt

    def calc_first_derivative(self, t):
        xt = self.a1 + 2 * self.a2 * t + \
             3 * self.a3 * t ** 2 + 4 * self.a4 * t ** 3 + 5 * self.a5 * t ** 4
        return xt

    def calc_second_derivative(self, t):
        xt = 2 * self.a2 + \
             6 * self.a3 * t + 12 * self.a4 * t ** 2 + 20 * self.a5 * t ** 3
        return xt

    def calc_third_derivative(self, t):
        xt = 6 * self.a3 + 24 * self.a4 * t + 60 * self.a5 * t ** 2
        return xt


class QuinticPolynomialPlanner:
    def __init__(self):
        pass
        
    def generate_trajectory(self, start_state, end_state, T, dt=0.1):
        """
        Generates a 2D trajectory using two Quintic Polynomials (one for x, one for y).
        start_state: [x, y, vx, vy, ax, ay]
        end_state: [x, y, vx, vy, ax, ay]
        T: Duration
        dt: Time step
        
        Returns: 
            times: [0, dt, ..., T]
            rx: x positions
            ry: y positions
            rv: velocities
            ra: accelerations
        """
        sx, sy, svx, svy, sax, say = start_state
        ex, ey, evx, evy, eax, eay = end_state
        
        # Polynomial for X
        qp_x = QuinticPolynomial(sx, svx, sax, ex, evx, eax, T)
        # Polynomial for Y
        qp_y = QuinticPolynomial(sy, svy, say, ey, evy, eay, T)
        
        times = np.arange(0.0, T + dt, dt)
        
        rx, ry, rvx, rvy, rax, ray = [], [], [], [], [], []
        
        for t in times:
            rx.append(qp_x.calc_point(t))
            ry.append(qp_y.calc_point(t))
            
            vx = qp_x.calc_first_derivative(t)
            vy = qp_y.calc_first_derivative(t)
            rvx.append(vx)
            rvy.append(vy)
            
            ax = qp_x.calc_second_derivative(t)
            ay = qp_y.calc_second_derivative(t)
            rax.append(ax)
            ray.append(ay)
            
        return times, rx, ry, rvx, rvy, rax, ray
