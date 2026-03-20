#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include <cmath>
#include <vector>
#include <algorithm>

namespace py = pybind11;


// =============================================================================
// bresenham_line
// =============================================================================

std::vector<std::pair<int, int>> bresenham_line(int y0, int x0, int y1, int x1) {
    std::vector<std::pair<int, int>> points;
    int dx = std::abs(x1 - x0);
    int dy = std::abs(y1 - y0);
    int sx = (x0 < x1) ? 1 : -1;
    int sy = (y0 < y1) ? 1 : -1;
    int err = dx - dy;
    int x = x0, y = y0;

    while (true) {
        points.push_back({y, x});
        if (x == x1 && y == y1) break;

        int e2 = 2 * err;
        if (e2 > -dy) {
            err -= dy;
            x += sx;
        }
        if (e2 < dx) {
            err += dx;
            y += sy;
        }
    }
    return points;
}


// =============================================================================
// local_pca_normal
//
// Computes the local unit normal vector at skeleton point (y, x) using PCA
// over neighbouring skeleton points within a circular window of radius window_size.
//
// The 2x2 covariance matrix has the closed-form eigenvector solution:
//   For symmetric M = [[a, b], [b, c]], the principal eigenvector (largest eigenvalue) is:
//     if b == 0: eigvec = (1,0) if a>=c else (0,1)
//     else:      eigvec = normalise([b, lambda_max - a])
//   where lambda_max = 0.5 * ((a+c) + sqrt((a-c)^2 + 4b^2))
//
// Normal is then obtained by rotating the tangent 90 degrees: (-tx_x, tx_y) -> normalised.
//
// Returns (ny, nx) as a pair of doubles. Returns (0.0, 0.0) if insufficient points.
// =============================================================================

std::pair<double, double> local_pca_normal(
    py::array_t<bool, py::array::c_style | py::array::forcecast> skeleton,
    int y, int x, int window_size = 15)
{
    auto buf = skeleton.unchecked<2>();
    const int h = static_cast<int>(buf.shape(0));
    const int w = static_cast<int>(buf.shape(1));

    const int y_min = std::max(0, y - window_size);
    const int y_max = std::min(h, y + window_size + 1);
    const int x_min = std::max(0, x - window_size);
    const int x_max = std::min(w, x + window_size + 1);

    // Collect skeleton points within the circular window
    std::vector<double> ys, xs;
    ys.reserve(128);
    xs.reserve(128);

    const double ws2 = static_cast<double>(window_size) * window_size;
    for (int py_ = y_min; py_ < y_max; ++py_) {
        for (int px_ = x_min; px_ < x_max; ++px_) {
            if (!buf(py_, px_)) continue;
            double dy = py_ - y;
            double dx = px_ - x;
            if (dy * dy + dx * dx <= ws2) {
                ys.push_back(static_cast<double>(py_));
                xs.push_back(static_cast<double>(px_));
            }
        }
    }

    const int n = static_cast<int>(ys.size());
    if (n < 3) return {0.0, 0.0};

    // Compute means
    double mean_y = 0.0, mean_x = 0.0;
    for (int i = 0; i < n; ++i) { mean_y += ys[i]; mean_x += xs[i]; }
    mean_y /= n;
    mean_x /= n;

    // Compute 2x2 covariance matrix elements (unbiased)
    // cov = [[cyy, cyx], [cyx, cxx]]
    double cyy = 0.0, cxx = 0.0, cyx = 0.0;
    for (int i = 0; i < n; ++i) {
        double dy = ys[i] - mean_y;
        double dx = xs[i] - mean_x;
        cyy += dy * dy;
        cxx += dx * dx;
        cyx += dy * dx;
    }
    const double inv = 1.0 / (n - 1);
    cyy *= inv;
    cxx *= inv;
    cyx *= inv;

    // Closed-form principal eigenvector of 2x2 symmetric matrix [[cyy, cyx],[cyx, cxx]]
    // tangent = [ty, tx] (principal direction = fibre direction)
    double ty, tx;
    if (std::abs(cyx) < 1e-12) {
        // Off-diagonal is zero: eigenvectors are axis-aligned
        if (cyy >= cxx) { ty = 1.0; tx = 0.0; }
        else            { ty = 0.0; tx = 1.0; }
    } else {
        double trace_half = 0.5 * (cyy + cxx);
        double diff_half  = 0.5 * (cyy - cxx);
        double lambda_max = trace_half + std::sqrt(diff_half * diff_half + cyx * cyx);
        // Eigenvector for lambda_max: [cyx, lambda_max - cyy] (unnormalised)
        ty = cyx;
        tx = lambda_max - cyy;
        double norm = std::sqrt(ty * ty + tx * tx);
        if (norm < 1e-12) return {0.0, 0.0};
        ty /= norm;
        tx /= norm;
    }

    // Rotate tangent 90 degrees to get normal: (ty, tx) -> (-tx, ty)
    double ny_ = -tx;
    double nx_ =  ty;

    // Normalise (should already be unit, but guard against numerical drift)
    double norm = std::sqrt(ny_ * ny_ + nx_ * nx_);
    if (norm < 1e-12) return {0.0, 0.0};

    return {ny_ / norm, nx_ / norm};
}


// =============================================================================
// pybind11 module
// =============================================================================

PYBIND11_MODULE(measure_tool, m) {
    m.doc() = "Measurement tools for fibre diameter measurement, including computation-intensive functions built in C++";

    m.def("bresenham_line", &bresenham_line,
          py::arg("y0"), py::arg("x0"), py::arg("y1"), py::arg("x1"),
          "Return point coordinate set using Bresenham's algorithm");

    m.def("local_pca_normal", &local_pca_normal,
          py::arg("skeleton"), py::arg("y"), py::arg("x"), py::arg("window_size") = 15,
          "Compute local unit normal vector at skeleton point (y, x) via PCA over a circular window. "
          "Returns (ny, nx). Returns (0.0, 0.0) if insufficient points.");
}