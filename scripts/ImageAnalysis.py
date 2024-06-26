import rospy
import numpy as np
import open3d as o3d
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import scipy.interpolate
import scipy.stats
import sensor_msgs
import sensor_msgs.point_cloud2
import sensor_msgs.msg
from scipy.spatial import cKDTree
np.float =float  # temp fix for ros_numpy
import ros_numpy
import std_msgs.msg

class tree(object):
    """
    Compute the score of query points based on the scores of their k-nearest neighbours,
    weighted by the inverse of their distances.

    @reference:
    https://en.wikipedia.org/wiki/Inverse_distance_weighting

    Arguments:
    ----------
        X: (N, d) ndarray
            Coordinates of N sample points in a d-dimensional space.
        z: (N,) ndarray
            Corresponding scores.
        leafsize: int (default 10)
            Leafsize of KD-tree data structure;
            should be less than 20.

    Returns:
    --------
        tree instance: object

    Example:
    --------

    # 'train'
    idw_tree = tree(X1, z1)

    # 'test'
    spacing = np.linspace(-5., 5., 100)
    X2 = np.meshgrid(spacing, spacing)
    X2 = np.reshape(X2, (2, -1)).T
    z2 = idw_tree(X2)

    See also:
    ---------
    demo()

    """

    
    # See https://github.com/paulbrodersen/inverse_distance_weighting
    # for the original GitHub repository containing this class
    
    # This class uses the below license:

    # BEGIN LICENSE
    # Copyright (C) 2016 Paul Brodersen <paulbrodersen+idw@gmail.com>

    # Author: Paul Brodersen <paulbrodersen+idw@gmail.com>
    
    # This program is free software; you can redistribute it and/or
    # modify it under the terms of the GNU General Public License
    # as published by the Free Software Foundation; either version 3
    # of the License, or (at your option) any later version.
    
    # This program is distributed in the hope that it will be useful,
    # but WITHOUT ANY WARRANTY; without even the implied warranty of
    # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    # GNU General Public License for more details.
    
    # You should have received a copy of the GNU General Public License
    # along with this program. If not, see <http://www.gnu.org/licenses/>.
    # END LICENSE
    
    def __init__(self, X=None, z=None, leafsize=10):
        if not X is None:
            self.tree = cKDTree(X, leafsize=leafsize )
        if not z is None:
            self.z = np.array(z)

    def fit(self, X=None, z=None, leafsize=10):
        """
        Instantiate KDtree for fast query of k-nearest neighbour distances.

        Arguments:
        ----------
            X: (N, d) ndarray
                Coordinates of N sample points in a d-dimensional space.
            z: (N,) ndarray
                Corresponding scores.
            leafsize: int (default 10)
                Leafsize of KD-tree data structure;
                should be less than 20.

        Returns:
        --------
            idw_tree instance: object

        Notes:
        -------
        Wrapper around __init__().

        """
        return self.__init__(X, z, leafsize)

    def __call__(self, X, k=3, eps=1e-6, p=2, regularize_by=1e-9):
        """
        Compute the score of query points based on the scores of their k-nearest neighbours,
        weighted by the inverse of their distances.

        Arguments:
        ----------
            X: (N, d) ndarray
                Coordinates of N query points in a d-dimensional space.

            k: int (default 6)
                Number of nearest neighbours to use.

            p: int or inf
                Which Minkowski p-norm to use.
                1 is the sum-of-absolute-values "Manhattan" distance
                2 is the usual Euclidean distance
                infinity is the maximum-coordinate-difference distance

            eps: float (default 1e-6)
                Return approximate nearest neighbors; the k-th returned value
                is guaranteed to be no further than (1+eps) times the
                distance to the real k-th nearest neighbor.

            regularise_by: float (default 1e-9)
                Regularise distances to prevent division by zero
                for sample points with the same location as query points.

        Returns:
        --------
            z: (N,) ndarray
                Corresponding scores.
        """
        self.distances, self.idx = self.tree.query(X, k, eps=eps, p=p)
        self.distances += regularize_by
        weights = self.z[self.idx.ravel()].reshape(self.idx.shape)
        mw = np.sum(weights/self.distances, axis=1) / np.sum(1./self.distances, axis=1)
        return mw

    def transform(self, X, k=3, p=2, eps=1e-6, regularize_by=1e-9):
        """
        Compute the score of query points based on the scores of their k-nearest neighbours,
        weighted by the inverse of their distances.

        Arguments:
        ----------
            X: (N, d) ndarray
                Coordinates of N query points in a d-dimensional space.

            k: int (default 6)
                Number of nearest neighbours to use.

            p: int or inf
                Which Minkowski p-norm to use.
                1 is the sum-of-absolute-values "Manhattan" distance
                2 is the usual Euclidean distance
                infinity is the maximum-coordinate-difference distance

            eps: float (default 1e-6)
                Return approximate nearest neighbors; the k-th returned value
                is guaranteed to be no further than (1+eps) times the
                distance to the real k-th nearest neighbor.

            regularise_by: float (default 1e-9)
                Regularise distances to prevent division by zero
                for sample points with the same location as query points.

        Returns:
        --------
            z: (N,) ndarray
                Corresponding scores.

        Notes:
        ------

        Wrapper around __call__().
        """
        return self.__call__(X, k, eps, p, regularize_by)


def optimizer(ground_pcl, distance_to_top_leg, distance_to_right_leg, resolution):
    # Convert ground point cloud to digital terrain model
    grid_size = [distance_to_right_leg/resolution[0], distance_to_top_leg/resolution[1]]
    # grid_size = [0.02, 0.02]
    x_min, x_max = np.min(ground_pcl[:, 0]), np.max(ground_pcl[:, 0])
    y_min, y_max = np.min(ground_pcl[:, 1]), np.max(ground_pcl[:, 1])
    xGrid = np.arange(x_min, x_max + grid_size[0], grid_size[0])
    yGrid = np.arange(y_min, y_max + grid_size[1], grid_size[1])
    XGrid, YGrid = np.meshgrid(xGrid, yGrid)
    idw_tree = tree(ground_pcl[:, 0:2], ground_pcl[:,2], leafsize = 5)
    X2 = np.meshgrid(xGrid, yGrid)
    grid_shape = X2[0].shape
    X2 = np.reshape(X2, (2, -1)).T
    z2 = idw_tree(X2)
    terrainModel = z2.reshape(grid_shape)

    # distance_to_top_leg = 0.08
    # distance_to_right_leg = 0.06
    distance_to_top_leg_points = int(distance_to_top_leg/grid_size[1])
    distance_to_right_leg_points = int(distance_to_right_leg/grid_size[0])

    # get locations of each leg as a function of the position of bottom left
    # leg
    bottom_left_height = terrainModel[0:(len(yGrid) - distance_to_top_leg_points), 0:(len(xGrid) - distance_to_right_leg_points)]
    bottom_right_height = terrainModel[0:(len(yGrid) - distance_to_top_leg_points), (distance_to_right_leg_points + 1 - 1):(len(xGrid))]
    top_left_height = terrainModel[(distance_to_top_leg_points + 1 - 1):len(yGrid), 0:(len(xGrid) - distance_to_right_leg_points)]
    top_right_height = terrainModel[(distance_to_top_leg_points + 1 - 1):len(yGrid), (distance_to_right_leg_points + 1 - 1):(len(xGrid))]

    max_leg_height = np.fmax(np.fmax(np.fmax(bottom_left_height, bottom_right_height), top_left_height), top_right_height)
    min_leg_height = np.fmin(np.fmin(np.fmin(bottom_left_height, bottom_right_height), top_left_height), top_right_height)
    maximum_leg_height_difference = max_leg_height - min_leg_height

    # prepare plot of optimal landing locations
    fig, ax = plt.subplots()
    contourf_ = ax.contourf(XGrid[0:(len(yGrid) - distance_to_top_leg_points), 0:(len(xGrid) - distance_to_right_leg_points)], 
                YGrid[0:(len(yGrid) - distance_to_top_leg_points), 0:(len(xGrid) - distance_to_right_leg_points)], 
                maximum_leg_height_difference, 100, cmap='viridis', levels=np.linspace(0,0.2,100), extend = 'max')
    plt.xlabel('x (m)')
    plt.ylabel('y (m)')
    plt.title('Leg Differences (m)')
    plt.ylim()
    cbar = fig.colorbar(contourf_,ticks=[0,0.04,0.08,0.12,0.16,0.2])
    fig.canvas.draw()
    img_np = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
    img_np = img_np.reshape(fig.canvas.get_width_height()[::-1] + (3,))
    plt.close()

    # prepare plot of DEM
    fig, ax = plt.subplots()
    contourf_ = ax.contourf(XGrid[0:(len(yGrid)), 0:(len(xGrid))], 
                YGrid[0:(len(yGrid)), 0:(len(xGrid))], 
                terrainModel, 100, cmap='viridis')
    plt.xlabel('x (m)')
    plt.ylabel('y (m)')
    plt.title('Digital Elevation Model (m)')
    plt.ylim()
    fig.colorbar(contourf_)
    fig.canvas.draw()
    DEM_np = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
    DEM_np = DEM_np.reshape(fig.canvas.get_width_height()[::-1] + (3,))
    plt.close()

    return(img_np, DEM_np)

def convert_numpy_to_pc2_msg(numpy_pcl):
    fields = [sensor_msgs.msg.PointField('x', 0, sensor_msgs.msg.PointField.FLOAT32, 1),
              sensor_msgs.msg.PointField('y', 4, sensor_msgs.msg.PointField.FLOAT32, 1),
              sensor_msgs.msg.PointField('z', 8, sensor_msgs.msg.PointField.FLOAT32, 1)]
    header = std_msgs.msg.Header()
    header.frame_id = "map"
    header.stamp = rospy.Time.now()
    pcl_msg = sensor_msgs.point_cloud2.create_cloud(header,fields, numpy_pcl)
    return(pcl_msg)

def convert_numpy_to_img_msg(img_np):
    return(ros_numpy.msgify(sensor_msgs.msg.Image, img_np, encoding = "rgb8"))

def point_cloud_callback(point_cloud_msg, args):
    # unpack args
    pub_legs = args[0]
    # pub_ground = args[1]
    pub_DEM = args[1]
    distance_to_top_leg = args[2]
    distance_to_right_leg = args[3]
    resolution = args[4]

    # Convert ROS PointCloud2 message to Open3D PointCloud
    points_list = list(sensor_msgs.point_cloud2.read_points(point_cloud_msg, skip_nans=True, field_names = ("x", "y", "z")))
    points_list = np.asarray(points_list)

    if points_list.size > 3:
        # Run optimizer
        img_legs, img_DEM = optimizer(points_list, distance_to_top_leg, distance_to_right_leg, resolution)

        # publish results of optimizer
        pub_legs.publish(convert_numpy_to_img_msg(img_legs))
        pub_DEM.publish(convert_numpy_to_img_msg(img_DEM))
        # pub_ground.publish(convert_numpy_to_pc2_msg(ground_pcl))
        # pub_nonground.publish(convert_numpy_to_pc2_msg(nonground_pcl))

def main():
    # Initialize the ROS node
    rospy.init_node('point_cloud_optimizer', anonymous=True)

    leg_position_rb = rospy.get_param('/leg_positions/rb')
    leg_position_lf = rospy.get_param('/leg_positions/lf')
    resolution = rospy.get_param('/terrain_model_resolution')

    distance_to_top_leg = abs(leg_position_rb[1] - leg_position_lf[1])
    distance_to_right_leg = abs(leg_position_rb[0] - leg_position_lf[0])

    print(distance_to_top_leg, distance_to_right_leg)
    # Create a publisher to publish plot
    pub_legs = rospy.Publisher('/optimizer/optimal_landing_locations', sensor_msgs.msg.Image, queue_size = 1)
    # pub_ground = rospy.Publisher('/optimizer/ground_point_cloud', sensor_msgs.msg.PointCloud2, queue_size = 1)
    # pub_nonground = rospy.Publisher('/optimizer/non_ground_point_cloud', sensor_msgs.msg.PointCloud2, queue_size = 1)
    pub_DEM = rospy.Publisher('/optimizer/digital_elevation_model', sensor_msgs.msg.Image, queue_size = 1)

    # Create a subscriber to the point cloud topic
    # Replace 'input_point_cloud_topic' with your actual topic name
    rospy.Subscriber('/zedm/zed_node/mapping/fused_cloud', sensor_msgs.msg.PointCloud2, point_cloud_callback, (pub_legs, pub_DEM, distance_to_top_leg, distance_to_right_leg, resolution), queue_size=1)

    # Spin to keep the script for exiting
    rospy.spin()

if __name__ == '__main__':
    try:
        main()
    except rospy.ROSInterruptException:
        pass

