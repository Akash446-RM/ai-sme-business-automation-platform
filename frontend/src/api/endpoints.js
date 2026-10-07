import api from './client';

/** Every backend call lives here so components never build URLs themselves. */

export const authApi = {
  login: (email, password) =>
    api.post('/auth/login', { email, password }).then((r) => r.data),
  register: (payload) => api.post('/auth/register', payload).then((r) => r.data),
  me: () => api.get('/auth/me').then((r) => r.data),
  changePassword: (payload) =>
    api.post('/auth/change-password', payload).then((r) => r.data),
  listUsers: () => api.get('/auth/users').then((r) => r.data),
};

export const dashboardApi = {
  summary: () => api.get('/dashboard/summary').then((r) => r.data),
  kpis: () => api.get('/dashboard/kpis').then((r) => r.data),
  insights: (limit = 6) =>
    api.get('/dashboard/insights', { params: { limit } }).then((r) => r.data),
};

export const productApi = {
  list: (params) => api.get('/products', { params }).then((r) => r.data),
  get: (id) => api.get(`/products/${id}`).then((r) => r.data),
  create: (payload) => api.post('/products', payload).then((r) => r.data),
  update: (id, payload) => api.put(`/products/${id}`, payload).then((r) => r.data),
  remove: (id) => api.delete(`/products/${id}`).then((r) => r.data),
  deactivate: (id) => api.post(`/products/${id}/deactivate`).then((r) => r.data),
  adjustStock: (id, payload) =>
    api.post(`/products/${id}/adjust-stock`, payload).then((r) => r.data),
  categories: () => api.get('/products/categories').then((r) => r.data),
  suppliers: () => api.get('/products/suppliers').then((r) => r.data),
  search: (q, limit = 10) =>
    api.get('/products/search', { params: { q, limit } }).then((r) => r.data),
};

export const customerApi = {
  list: (params) => api.get('/customers', { params }).then((r) => r.data),
  get: (id) => api.get(`/customers/${id}`).then((r) => r.data),
  create: (payload) => api.post('/customers', payload).then((r) => r.data),
  update: (id, payload) => api.put(`/customers/${id}`, payload).then((r) => r.data),
  remove: (id) => api.delete(`/customers/${id}`).then((r) => r.data),
  cities: () => api.get('/customers/cities').then((r) => r.data),
};

export const employeeApi = {
  list: (params) => api.get('/employees', { params }).then((r) => r.data),
  get: (id) => api.get(`/employees/${id}`).then((r) => r.data),
  create: (payload) => api.post('/employees', payload).then((r) => r.data),
  update: (id, payload) => api.put(`/employees/${id}`, payload).then((r) => r.data),
  remove: (id) => api.delete(`/employees/${id}`).then((r) => r.data),
  roles: () => api.get('/employees/roles').then((r) => r.data),
  performance: (id) => api.get(`/employees/${id}/performance`).then((r) => r.data),
};

export const salesApi = {
  list: (params) => api.get('/sales', { params }).then((r) => r.data),
  get: (id) => api.get(`/sales/${id}`).then((r) => r.data),
  create: (payload) => api.post('/sales', payload).then((r) => r.data),
  recent: (limit = 10) =>
    api.get('/sales/recent', { params: { limit } }).then((r) => r.data),
  void: (id) => api.delete(`/sales/${id}`).then((r) => r.data),
};

export const inventoryApi = {
  overview: () => api.get('/inventory/overview').then((r) => r.data),
  stock: (params) => api.get('/inventory/stock', { params }).then((r) => r.data),
  recommendations: (params) =>
    api.get('/inventory/recommendations', { params }).then((r) => r.data),
  recommendationFor: (id, horizonDays = 7) =>
    api
      .get(`/inventory/recommendations/${id}`, { params: { horizon_days: horizonDays } })
      .then((r) => r.data),
  movement: (params) => api.get('/inventory/movement', { params }).then((r) => r.data),
  deadStock: (limit = 20) =>
    api.get('/inventory/dead-stock', { params: { limit } }).then((r) => r.data),
  valuation: () => api.get('/inventory/valuation').then((r) => r.data),
  transactions: (params) =>
    api.get('/inventory/transactions', { params }).then((r) => r.data),
};

export const analyticsApi = {
  revenue: () => api.get('/analytics/revenue').then((r) => r.data),
  summary: (params) => api.get('/analytics/summary', { params }).then((r) => r.data),
  salesTrend: (params) => api.get('/analytics/sales-trend', { params }).then((r) => r.data),
  products: (params) => api.get('/analytics/products', { params }).then((r) => r.data),
  categories: (params) => api.get('/analytics/categories', { params }).then((r) => r.data),
  customers: (params) => api.get('/analytics/customers', { params }).then((r) => r.data),
  employees: (params) => api.get('/analytics/employees', { params }).then((r) => r.data),
  paymentMix: (params) => api.get('/analytics/payment-mix', { params }).then((r) => r.data),
  hourlyPattern: (params) =>
    api.get('/analytics/hourly-pattern', { params }).then((r) => r.data),
  weekdayPattern: (params) =>
    api.get('/analytics/weekday-pattern', { params }).then((r) => r.data),
  demandShifts: (params) =>
    api.get('/analytics/demand-shifts', { params }).then((r) => r.data),
};

export const forecastApi = {
  status: () => api.get('/forecasting/status').then((r) => r.data),
  sales: (horizonDays = 7) =>
    api.get('/forecasting/sales', { params: { horizon_days: horizonDays } }).then((r) => r.data),
  demand: (productId, horizonDays = 7) =>
    api
      .get(`/forecasting/demand/${productId}`, { params: { horizon_days: horizonDays } })
      .then((r) => r.data),
  demandSummary: (params) =>
    api.get('/forecasting/demand-summary', { params }).then((r) => r.data),
  refreshCache: () => api.post('/forecasting/refresh-cache').then((r) => r.data),
};

export const alertApi = {
  list: (params) => api.get('/alerts', { params }).then((r) => r.data),
  summary: () => api.get('/alerts/summary').then((r) => r.data),
  scan: (horizonDays = 7) =>
    api.post('/alerts/scan', null, { params: { horizon_days: horizonDays } }).then((r) => r.data),
  updateStatus: (id, status) =>
    api.patch(`/alerts/${id}`, { status }).then((r) => r.data),
};

export const reportApi = {
  sales: (params) => api.get('/reports/sales', { params }).then((r) => r.data),
  revenue: (params) => api.get('/reports/revenue', { params }).then((r) => r.data),
  inventory: (params) => api.get('/reports/inventory', { params }).then((r) => r.data),
  products: (params) => api.get('/reports/products', { params }).then((r) => r.data),
  customers: (params) => api.get('/reports/customers', { params }).then((r) => r.data),
  businessSummary: (params) =>
    api.get('/reports/business-summary', { params }).then((r) => r.data),
};

export const aiApi = {
  chat: (question, includeData = true) =>
    api.post('/ai/chat', { question, include_data: includeData }).then((r) => r.data),
  status: () => api.get('/ai/status').then((r) => r.data),
  suggestions: () => api.get('/ai/suggestions').then((r) => r.data),
};
