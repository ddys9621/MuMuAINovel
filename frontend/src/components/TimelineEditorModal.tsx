import React, { useState, useEffect } from 'react';
import { Modal, Form, Input, Button, Table, InputNumber, Space, Alert, message } from 'antd';
import { PlusOutlined, DeleteOutlined, EditOutlined } from '@ant-design/icons';
import type { TimelineData, TimelineBeat, PlotLine } from '../types';

interface TimelineEditorModalProps {
  visible: boolean;
  plotLine: PlotLine | null;
  onClose: () => void;
  onSave: (data: TimelineData) => Promise<void>;
}

const TimelineEditorModal: React.FC<TimelineEditorModalProps> = ({
  visible,
  plotLine,
  onClose,
  onSave,
}) => {
  // const [form] = Form.useForm();
  const [beats, setBeats] = useState<TimelineBeat[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingBeat, setEditingBeat] = useState<TimelineBeat | null>(null);
  const [beatModalVisible, setBeatModalVisible] = useState(false);
  const [beatForm] = Form.useForm();

  // 初始化表单数据
  useEffect(() => {
    if (visible && plotLine?.timeline_data) {
      const timelineData = plotLine.timeline_data as TimelineData;
      setBeats(timelineData.beats || []);
    } else if (visible) {
      // 新建时的默认值
      setBeats([]);
    }
  }, [visible, plotLine]);

  // 计算权重总和
  const totalWeight = beats.reduce((sum, beat) => sum + beat.weight, 0);
  const isWeightValid = Math.abs(totalWeight - 1.0) < 0.01;

  // 保存时间线
  const handleSave = async () => {
    try {
      // 验证权重总和
      if (!isWeightValid) {
        message.error('节点权重总和必须为 1.0');
        return;
      }

      // 验证至少有一个节点
      if (beats.length === 0) {
        message.error('至少需要添加一个节点');
        return;
      }

      setLoading(true);

      const timelineData: TimelineData = {
        beats: beats,
      };

      await onSave(timelineData);
      message.success('时间线保存成功');
      onClose();
    } catch (error) {
      console.error('保存失败:', error);
    } finally {
      setLoading(false);
    }
  };

  // 添加/编辑节点
  const handleSaveBeat = async () => {
    try {
      const values = await beatForm.validateFields();
      
      if (editingBeat) {
        // 编辑现有节点，保留原有 index 等字段
        setBeats(beats.map(b =>
          b.index === editingBeat.index ? { ...b, ...values, index: b.index } : b
        ));
      } else {
        // 添加新节点
        const newIndex = beats.length > 0 ? Math.max(...beats.map(b => b.index)) + 1 : 1;
        setBeats([...beats, { ...values, index: newIndex }]);
      }
      
      setBeatModalVisible(false);
      beatForm.resetFields();
      setEditingBeat(null);
    } catch (error) {
      console.error('节点保存失败:', error);
    }
  };

  // 删除节点
  const handleDeleteBeat = (index: number) => {
    setBeats(beats.filter(b => b.index !== index));
  };

  // 打开节点编辑对话框
  const handleEditBeat = (beat: TimelineBeat) => {
    setEditingBeat(beat);
    beatForm.setFieldsValue(beat);
    setBeatModalVisible(true);
  };

  // 打开新增节点对话框
  const handleAddBeat = () => {
    setEditingBeat(null);
    beatForm.resetFields();
    beatForm.setFieldsValue({
      key: '',
      title: '',
      description: '',
      weight: 0.25,
    });
    setBeatModalVisible(true);
  };

  // 节点表格列定义
  const beatColumns = [
    {
      title: '序号',
      dataIndex: 'index',
      key: 'index',
      width: 80,
    },
    {
      title: '标识',
      dataIndex: 'key',
      key: 'key',
      width: 120,
    },
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
    },
    {
      title: '权重',
      dataIndex: 'weight',
      key: 'weight',
      width: 100,
      render: (weight: number) => weight.toFixed(2),
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: any, record: TimelineBeat) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEditBeat(record)}
          >
            编辑
          </Button>
          <Button
            type="link"
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDeleteBeat(record.index)}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Modal
        title={`编辑时间线 - ${plotLine?.title || ''}`}
        open={visible}
        onCancel={onClose}
        width={800}
        footer={[
          <Button key="cancel" onClick={onClose}>
            取消
          </Button>,
          <Button key="save" type="primary" loading={loading} onClick={handleSave}>
            保存
          </Button>,
        ]}
      >
        <div>
          <div style={{ marginBottom: 16 }}>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleAddBeat}
            >
              添加节点
            </Button>
            <Alert
              type={isWeightValid ? 'success' : 'warning'}
              message={`当前权重总和: ${totalWeight.toFixed(2)} ${
                isWeightValid ? '✓' : '⚠️ 必须为 1.0'
              }`}
              style={{ marginTop: 8 }}
            />
          </div>
          <Table
            dataSource={beats}
            columns={beatColumns}
            rowKey="index"
            pagination={false}
            size="small"
          />
        </div>
      </Modal>

      {/* 节点编辑对话框 */}
      <Modal
        title={editingBeat ? '编辑节点' : '添加节点'}
        open={beatModalVisible}
        onCancel={() => {
          setBeatModalVisible(false);
          beatForm.resetFields();
          setEditingBeat(null);
        }}
        onOk={handleSaveBeat}
      >
        <Form form={beatForm} layout="vertical">
          <Form.Item
            label="标识"
            name="key"
            rules={[
              { required: true, message: '请输入节点标识' },
              { max: 50, message: '标识最多50个字符' },
            ]}
          >
            <Input placeholder="例如: opening, climax" />
          </Form.Item>

          <Form.Item
            label="标题"
            name="title"
            rules={[
              { required: true, message: '请输入节点标题' },
              { max: 200, message: '标题最多200个字符' },
            ]}
          >
            <Input placeholder="例如: 开端" />
          </Form.Item>

          <Form.Item label="描述" name="description">
            <Input.TextArea rows={3} placeholder="节点描述（可选）" />
          </Form.Item>

          <Form.Item
            label="权重"
            name="weight"
            rules={[
              { required: true, message: '请输入权重' },
              {
                type: 'number',
                min: 0,
                max: 1,
                message: '权重必须在 0-1 之间',
              },
            ]}
          >
            <InputNumber
              min={0}
              max={1}
              step={0.05}
              precision={2}
              style={{ width: '100%' }}
              placeholder="0.25"
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

export default TimelineEditorModal;

