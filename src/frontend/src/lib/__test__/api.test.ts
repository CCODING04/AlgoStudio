import {
  getTasks,
  getTask,
  createTask,
  dispatchTask,
  getHostStatus,
  getDeployWorkers,
  getDeployWorker,
  createDeployWorker,
} from '../api';

// Mock global fetch
global.fetch = jest.fn();

const mockedFetch = global.fetch as jest.MockedFunction<typeof global.fetch>;

describe('API Client', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('getTasks', () => {
    test('fetches tasks without status filter', async () => {
      const mockResponse = {
        items: [
          {
            task_id: 'train-001',
            task_type: 'train' as const,
            algorithm_name: 'test-algo',
            algorithm_version: 'v1',
            status: 'pending' as const,
            created_at: '2024-01-01T00:00:00Z',
            started_at: null,
            completed_at: null,
            assigned_node: null,
            error: null,
            progress: null,
          },
        ],
        next_cursor: null,
        has_more: false,
      };

      mockedFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      } as Response);

      const result = await getTasks();

      expect(mockedFetch).toHaveBeenCalledWith('/api/proxy/tasks', { cache: 'no-store' });
      expect(result).toEqual(mockResponse.items);
    });

    test('fetches tasks with status filter', async () => {
      mockedFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ items: [], next_cursor: null, has_more: false }),
      } as Response);

      await getTasks('running');

      expect(mockedFetch).toHaveBeenCalledWith('/api/proxy/tasks?status=running', { cache: 'no-store' });
    });

    test('throws error when response is not ok', async () => {
      mockedFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      } as Response);

      await expect(getTasks()).rejects.toThrow('Failed to fetch tasks');
    });

    test('returns empty array when items is undefined', async () => {
      mockedFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ items: undefined, next_cursor: null, has_more: false }),
      } as Response);

      const result = await getTasks();

      expect(result).toEqual([]);
    });
  });

  describe('getTask', () => {
    test('fetches single task by id', async () => {
      const mockTask = {
        task_id: 'train-001',
        task_type: 'train' as const,
        algorithm_name: 'test-algo',
        algorithm_version: 'v1',
        status: 'completed' as const,
        created_at: '2024-01-01T00:00:00Z',
        started_at: '2024-01-01T00:01:00Z',
        completed_at: '2024-01-01T00:10:00Z',
        assigned_node: '192.168.0.126',
        error: null,
        progress: 100,
      };

      mockedFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTask),
      } as Response);

      const result = await getTask('train-001');

      expect(mockedFetch).toHaveBeenCalledWith('/api/proxy/tasks/train-001', { cache: 'no-store' });
      expect(result).toEqual(mockTask);
    });

    test('throws error when task fetch fails', async () => {
      mockedFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
      } as Response);

      await expect(getTask('nonexistent')).rejects.toThrow('Failed to fetch task');
    });
  });

  describe('createTask', () => {
    test('creates task with all fields', async () => {
      const request = {
        task_type: 'train' as const,
        algorithm_name: 'test-algo',
        algorithm_version: 'v1',
        data_path: '/data/train',
        config: { epochs: 10 },
      };

      const mockResponse = {
        task_id: 'train-002',
        task_type: 'train',
        algorithm_name: 'test-algo',
        algorithm_version: 'v1',
        status: 'pending',
        created_at: '2024-01-01T00:00:00Z',
        started_at: null,
        completed_at: null,
        assigned_node: null,
        error: null,
        progress: null,
      };

      mockedFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      } as Response);

      const result = await createTask(request);

      expect(mockedFetch).toHaveBeenCalledWith('/api/proxy/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });
      expect(result).toEqual(mockResponse);
    });

    test('creates task with minimal fields', async () => {
      const request = {
        task_type: 'infer' as const,
        algorithm_name: 'test-algo',
        algorithm_version: 'v1',
      };

      mockedFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ task_id: 'infer-001' }),
      } as Response);

      await createTask(request);

      expect(mockedFetch).toHaveBeenCalledWith('/api/proxy/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });
    });

    test('throws error when task creation fails', async () => {
      mockedFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
      } as Response);

      await expect(createTask({
        task_type: 'train',
        algorithm_name: 'test',
        algorithm_version: 'v1',
      })).rejects.toThrow('Failed to create task');
    });
  });

  describe('dispatchTask', () => {
    test('dispatches task without specific node', async () => {
      mockedFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ task_id: 'train-001', status: 'running' }),
      } as Response);

      await dispatchTask('train-001');

      expect(mockedFetch).toHaveBeenCalledWith('/api/proxy/tasks/train-001/dispatch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ node_id: null }),
      });
    });

    test('dispatches task to specific node', async () => {
      mockedFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ task_id: 'train-001', status: 'running', assigned_node: '192.168.0.115' }),
      } as Response);

      await dispatchTask('train-001', '192.168.0.115');

      expect(mockedFetch).toHaveBeenCalledWith('/api/proxy/tasks/train-001/dispatch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ node_id: '192.168.0.115' }),
      });
    });

    test('throws error when dispatch fails', async () => {
      mockedFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      } as Response);

      await expect(dispatchTask('train-001')).rejects.toThrow('Failed to dispatch task');
    });
  });

  describe('getHostStatus', () => {
    test('fetches cluster host status', async () => {
      const mockResponse = {
        cluster_nodes: [
          {
            node_id: 'node-1',
            ip: '192.168.0.126',
            status: 'online' as const,
            is_local: true,
            hostname: 'head-node',
            resources: {
              cpu: { total: 32, used: 4, physical_cores: 16, model: 'Intel i9', freq_mhz: 3600 },
              gpu: { total: 1, utilization: 50, memory_used: '8Gi', memory_total: '24Gi', name: 'RTX 4090' },
              memory: { total: '64Gi', used: '16Gi' },
              disk: { total: '1TB', used: '200GB' },
            },
          },
        ],
      };

      mockedFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      } as Response);

      const result = await getHostStatus();

      expect(mockedFetch).toHaveBeenCalledWith('/api/proxy/hosts', { cache: 'no-store' });
      expect(result).toEqual(mockResponse);
    });

    test('throws error when host status fetch fails', async () => {
      mockedFetch.mockResolvedValueOnce({
        ok: false,
        status: 503,
      } as Response);

      await expect(getHostStatus()).rejects.toThrow('Failed to fetch hosts');
    });
  });

  describe('getDeployWorkers', () => {
    test('fetches deploy workers list', async () => {
      const mockResponse = {
        items: [
          {
            task_id: 'deploy-001',
            status: 'running',
            step: 'Installing dependencies',
            step_index: 2,
            total_steps: 5,
            progress: 40,
            node_ip: '192.168.0.115',
          },
        ],
        total: 1,
      };

      mockedFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      } as Response);

      const result = await getDeployWorkers();

      expect(mockedFetch).toHaveBeenCalledWith('/api/proxy/deploy/workers', { cache: 'no-store' });
      expect(result).toEqual(mockResponse);
    });

    test('throws error when deploy workers fetch fails', async () => {
      mockedFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      } as Response);

      await expect(getDeployWorkers()).rejects.toThrow('Failed to fetch deploy workers');
    });
  });

  describe('getDeployWorker', () => {
    test('fetches single deploy worker by task id', async () => {
      const mockResponse = {
        task_id: 'deploy-001',
        status: 'completed',
        step: 'Deployment complete',
        step_index: 5,
        total_steps: 5,
        progress: 100,
        node_ip: '192.168.0.115',
        started_at: '2024-01-01T00:00:00Z',
        completed_at: '2024-01-01T00:05:00Z',
      };

      mockedFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      } as Response);

      const result = await getDeployWorker('deploy-001');

      expect(mockedFetch).toHaveBeenCalledWith('/api/proxy/deploy/worker/deploy-001', { cache: 'no-store' });
      expect(result).toEqual(mockResponse);
    });

    test('throws error when deploy worker fetch fails', async () => {
      mockedFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
      } as Response);

      await expect(getDeployWorker('nonexistent')).rejects.toThrow('Failed to fetch deploy worker');
    });
  });

  describe('createDeployWorker', () => {
    test('creates deploy worker with all fields', async () => {
      const request = {
        node_ip: '192.168.0.115',
        username: 'admin',
        password: 'secret',
        head_ip: '192.168.0.126',
        ray_port: 6379,
        proxy_url: 'http://proxy:8080',
      };

      const mockResponse = {
        task_id: 'deploy-002',
        message: 'Worker deployment started',
        node_ip: '192.168.0.115',
      };

      mockedFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      } as Response);

      const result = await createDeployWorker(request);

      expect(mockedFetch).toHaveBeenCalledWith('/api/proxy/deploy/worker', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });
      expect(result).toEqual(mockResponse);
    });

    test('creates deploy worker with minimal fields', async () => {
      const request = {
        node_ip: '192.168.0.115',
        password: 'secret',
        head_ip: '192.168.0.126',
      };

      mockedFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ task_id: 'deploy-003' }),
      } as Response);

      await createDeployWorker(request);

      expect(mockedFetch).toHaveBeenCalledWith('/api/proxy/deploy/worker', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });
    });

    test('throws error when deploy worker creation fails', async () => {
      mockedFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
      } as Response);

      await expect(createDeployWorker({
        node_ip: '192.168.0.115',
        password: 'secret',
        head_ip: '192.168.0.126',
      })).rejects.toThrow('Failed to create deploy worker');
    });
  });
});
