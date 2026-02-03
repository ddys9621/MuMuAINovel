import React, { useMemo, useEffect, useRef } from 'react';
import { Tooltip } from 'antd';

// 标注数据类型
export interface MemoryAnnotation {
  id: string;
  type: 'hook' | 'foreshadow' | 'plot_point' | 'character_event';
  title: string;
  content: string;
  importance: number;
  position: number;
  length: number;
  tags: string[];
  metadata: {
    strength?: number;
    foreshadowType?: 'planted' | 'resolved';
    relatedCharacters?: string[];
    [key: string]: any;
  };
}

// 文本片段类型
interface TextSegment {
  type: 'text' | 'annotated';
  content: string;
  annotation?: MemoryAnnotation;
}

interface AnnotatedTextProps {
  content: string;
  annotations: MemoryAnnotation[];
  onAnnotationClick?: (annotation: MemoryAnnotation) => void;
  activeAnnotationId?: string;
  scrollToAnnotation?: string;
  style?: React.CSSProperties;
}

// 类型颜色映射
const TYPE_COLORS = {
  hook: '#ff6b6b',
  foreshadow: '#6b7bff',
  plot_point: '#51cf66',
  character_event: '#ffd93d',
};

// 类型图标映射
const TYPE_ICONS = {
  hook: '🎣',
  foreshadow: '🌟',
  plot_point: '💎',
  character_event: '👤',
};

/**
 * 带标注的文本组件
 * 将记忆标注可视化地展示在章节文本中
 */
const AnnotatedText: React.FC<AnnotatedTextProps> = ({
  content,
  annotations,
  onAnnotationClick,
  activeAnnotationId,
  scrollToAnnotation,
  style,
}) => {
  const annotationRefs = useRef<Record<string, HTMLSpanElement | null>>({});

  // 当需要滚动到特定标注时
  useEffect(() => {
    if (scrollToAnnotation && annotationRefs.current[scrollToAnnotation]) {
      const element = annotationRefs.current[scrollToAnnotation];
      element?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }
  }, [scrollToAnnotation]);
  // 处理标注重叠和排序
  const processedAnnotations = useMemo(() => {
    if (!annotations || annotations.length === 0) {
      console.log('AnnotatedText: 没有标注数据');
      return [];
    }
    
    console.log(`AnnotatedText: 收到${annotations.length}个标注，内容长度${content.length}`);
    
    // 过滤掉无效位置的标注
    const validAnnotations = annotations.filter(
      (a) => a.position >= 0 && a.position < content.length
    );
    
    const invalidCount = annotations.length - validAnnotations.length;
    if (invalidCount > 0) {
      console.warn(`AnnotatedText: ${invalidCount}个标注位置无效，有效标注${validAnnotations.length}个`);
      console.log('无效标注:', annotations.filter(a => a.position < 0 || a.position >= content.length));
    }
    
    // 按位置排序
    return validAnnotations.sort((a, b) => a.position - b.position);
  }, [annotations, content]);

  // 将文本分割为带标注的片段
  const segments = useMemo(() => {
    if (processedAnnotations.length === 0) {
      return [{ type: 'text' as const, content }];
    }

    const result: TextSegment[] = [];
    let lastPos = 0;

    for (const annotation of processedAnnotations) {
      const { position, length } = annotation;
      
      // 添加普通文本片段
      if (position > lastPos) {
        result.push({
          type: 'text',
          content: content.slice(lastPos, position),
        });
      }

      // 添加标注片段
      const annotatedContent = content.slice(
        position,
        position + (length > 0 ? length : 30) // 如果没有长度，默认30字符
      );
      
      result.push({
        type: 'annotated',
        content: annotatedContent,
        annotation,
      });

      lastPos = position + (length > 0 ? length : 30);
    }

    // 添加剩余文本
    if (lastPos < content.length) {
      result.push({
        type: 'text',
        content: content.slice(lastPos),
      });
    }

    return result;
  }, [content, processedAnnotations]);

  // 渲染标注片段
  const renderAnnotatedSegment = (segment: TextSegment, index: number) => {
    if (segment.type === 'text') {
      return <span key={index}>{segment.content}</span>;
    }

    const { annotation } = segment;
    if (!annotation) return null;

    const color = TYPE_COLORS[annotation.type];
    const icon = TYPE_ICONS[annotation.type];
    const isActive = activeAnnotationId === annotation.id;

    // 工具提示内容
    const tooltipContent = (
      <div style={{ maxWidth: 300 }}>
        <div style={{ fontWeight: 'bold', marginBottom: 4 }}>
          {icon} {annotation.title}
        </div>
        <div style={{ fontSize: 12, opacity: 0.9 }}>
          {annotation.content.slice(0, 100)}
          {annotation.content.length > 100 ? '...' : ''}
        </div>
        <div style={{ marginTop: 8, fontSize: 11, opacity: 0.7 }}>
          重要性: {(annotation.importance * 10).toFixed(1)}/10
        </div>
        {annotation.tags && annotation.tags.length > 0 && (
          <div style={{ marginTop: 4, fontSize: 11 }}>
            {annotation.tags.map((tag, i) => (
              <span
                key={i}
                style={{
                  display: 'inline-block',
                  background: 'rgba(255,255,255,0.2)',
                  padding: '2px 6px',
                  borderRadius: 3,
                  marginRight: 4,
                }}
              >
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>
    );

    return (
      <Tooltip key={index} title={tooltipContent} placement="top">
        <span
          ref={(el) => {
            if (annotation) {
              annotationRefs.current[annotation.id] = el;
            }
          }}
          data-annotation-id={annotation?.id}
          className={`annotated-text ${isActive ? 'active' : ''}`}
          style={{
            position: 'relative',
            borderBottom: `2px solid ${color}`,
            cursor: 'pointer',
            backgroundColor: isActive ? `${color}22` : 'transparent',
            transition: 'all 0.2s',
            padding: '2px 0',
          }}
          onClick={() => onAnnotationClick?.(annotation)}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = `${color}33`;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = isActive
              ? `${color}22`
              : 'transparent';
          }}
        >
          {segment.content}
          <span
            style={{
              position: 'absolute',
              top: -20,
              left: '50%',
              transform: 'translateX(-50%)',
              fontSize: 14,
              pointerEvents: 'none',
            }}
          >
            {icon}
          </span>
        </span>
      </Tooltip>
    );
  };

  return (
    <div
      style={{
        lineHeight: 2,
        fontSize: 16,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        ...style,
      }}
    >
      {segments.map((segment, index) => renderAnnotatedSegment(segment, index))}
    </div>
  );
};

export default AnnotatedText;