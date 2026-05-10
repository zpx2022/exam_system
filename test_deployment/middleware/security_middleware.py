"""
安全传输中间件
实现基于HTTP Header的SM2+SM4密钥协商与敏感字段加密
统一采用敏感字段加密策略，X-Encrypt-Key常驻请求头
"""
import json
from django.utils.deprecation import MiddlewareMixin
from utils.gm_crypto import gm_crypto
from utils.data_classifier import classify_data, merge_encrypted_data


class CustomSecurityMiddleware(MiddlewareMixin):
    """
    安全传输中间件
    实现基于HTTP Header的密钥协商与全量响应加密
    """
    
    def process_request(self, request):
        """
        处理请求，实现基于HTTP Header的密钥协商机制
        统一采用敏感字段加密策略，X-Encrypt-Key常驻请求头
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # 检查HTTP Header中的加密密钥（常驻请求头）
        encrypt_key = request.META.get('HTTP_X_ENCRYPT_KEY')
        if encrypt_key:
            # 基于Header的安全传输模式
            try:
                # 1. 使用SM2私钥解密SM4密钥
                sm4_key = gm_crypto.sm2_decrypt_key(encrypt_key)
                
                # 2. 将SM4密钥挂载到request对象上，供后续使用
                request.current_sm4_key = sm4_key
                
                # 3. 如果请求包含Body，检查是否有加密字段需要解密
                if request.method in ['POST', 'PUT', 'PATCH'] and request.body:
                    content_type = request.META.get('CONTENT_TYPE', '')
                    if 'application/json' in content_type:
                        try:
                            data = json.loads(request.body)
                            
                            # 检查是否有加密字段（统一采用敏感字段策略）
                            if 'encrypted_fields' in data:
                                encrypted_fields = data['encrypted_fields']
                                
                                # 使用SM4密钥解密字段
                                decrypted_data_str = gm_crypto.sm4_decrypt_data(encrypted_fields, sm4_key)
                                decrypted_data = json.loads(decrypted_data_str)
                                
                                # 合并非加密数据和解密的数据
                                merged_data = merge_encrypted_data(data, decrypted_data)
                                
                                # 替换request.body
                                new_body = json.dumps(merged_data, ensure_ascii=False).encode('utf-8')
                                request._body = new_body
                                request.META['CONTENT_LENGTH'] = str(len(new_body))
                                
                                # 清除DRF的已解析数据缓存
                                if hasattr(request, '_data'):
                                    delattr(request, '_data')
                                if hasattr(request, '_full_data'):
                                    delattr(request, '_full_data')
                                if hasattr(request, '_files'):
                                    delattr(request, '_files')
                                    
                        except json.JSONDecodeError:
                            # JSON解析失败，可能是普通请求
                            pass
                        except Exception as e:
                            logger.error(f"解密请求字段失败: {str(e)}", exc_info=True)
                            # 解密失败时继续处理，让视图层处理原始数据
                            
            except Exception as e:
                logger.error(f"处理加密密钥失败: {str(e)}", exc_info=True)
                # 密钥解密失败时，不修改request，让视图层处理原始数据
        
        return None

    def process_response(self, request, response):
        """
        处理响应，对开启了安全传输的请求进行敏感字段响应加密
        统一采用敏感字段加密策略，X-Encrypt-Key常驻请求头
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # 检查request对象上是否存在current_sm4_key（常驻请求头机制）
        if hasattr(request, 'current_sm4_key') and request.current_sm4_key:
            try:
                # 获取当前请求的SM4密钥
                sm4_key = request.current_sm4_key
                
                # 提取原响应的完整内容
                if hasattr(response, 'content'):
                    content = response.content
                else:
                    # 如果没有content属性，尝试其他方式获取
                    content = getattr(response, 'data', b'{}')
                    if isinstance(content, str):
                        content = content.encode('utf-8')
                    elif isinstance(content, dict):
                        content = json.dumps(content, ensure_ascii=False).encode('utf-8')
                
                # 如果内容为空，返回空响应
                if not content:
                    return response
                
                # 解析响应内容，采用敏感字段加密策略
                try:
                    if isinstance(content, bytes):
                        content_str = content.decode('utf-8')
                    else:
                        content_str = str(content)
                    
                    # 解析JSON内容
                    response_data = json.loads(content_str)
                    
                    # 检查响应数据中是否包含敏感字段
                    if isinstance(response_data, dict):
                        from utils.data_classifier import classify_data
                        
                        # 如果响应有data字段且是字典类型，检查其中的敏感字段
                        if 'data' in response_data and isinstance(response_data['data'], dict):
                            data_content = response_data['data']
                            
                            # 处理分页数据
                            if isinstance(data_content, dict) and 'results' in data_content and isinstance(data_content['results'], list):
                                # 分页数据，检查每个结果项
                                results = data_content['results']
                                all_sensitive_data = []
                                non_sensitive_results = []
                                
                                for item in results:
                                    if isinstance(item, dict):
                                        classified = classify_data(item)
                                        if classified['sensitive']:
                                            # 有敏感字段，需要加密
                                            all_sensitive_data.append(classified['sensitive'])
                                            non_sensitive_results.append(classified['non_sensitive'])
                                        else:
                                            # 无敏感字段，直接使用
                                            non_sensitive_results.append(item)
                                
                                if all_sensitive_data:
                                    # 有敏感数据需要加密
                                    sensitive_data_str = json.dumps({'sensitive_results': all_sensitive_data})
                                    encrypted_sensitive = gm_crypto.sm4_encrypt_data(sensitive_data_str, sm4_key)
                                    
                                    # 构造加密响应
                                    encrypted_response_data = {
                                        'code': response_data.get('code', 200),
                                        'message': response_data.get('message', 'success'),
                                        'data': {
                                            'count': data_content.get('count', len(non_sensitive_results)),
                                            'results': non_sensitive_results,
                                            'encrypted_fields': encrypted_sensitive,
                                            'has_encryption': True
                                        }
                                    }
                                else:
                                    # 无敏感数据，返回原响应
                                    encrypted_response_data = response_data
                            
                            elif isinstance(data_content, dict):
                                # 单个对象数据，检查敏感字段
                                classified = classify_data(data_content)
                                if classified['sensitive']:
                                    # 有敏感字段需要加密
                                    sensitive_data_str = json.dumps(classified['sensitive'])
                                    encrypted_sensitive = gm_crypto.sm4_encrypt_data(sensitive_data_str, sm4_key)
                                    
                                    # 构造加密响应
                                    encrypted_response_data = {
                                        'code': response_data.get('code', 200),
                                        'message': response_data.get('message', 'success'),
                                        'data': {
                                            **classified['non_sensitive'],
                                            'encrypted_fields': encrypted_sensitive,
                                            'has_encryption': True
                                        }
                                    }
                                else:
                                    # 无敏感数据，返回原响应
                                    encrypted_response_data = response_data
                            else:
                                # data不是字典类型，返回原响应
                                encrypted_response_data = response_data
                        else:
                            # 没有data字段或data不是字典，检查整个响应对象
                            classified = classify_data(response_data)
                            if classified['sensitive']:
                                # 有敏感字段需要加密
                                sensitive_data_str = json.dumps(classified['sensitive'])
                                encrypted_sensitive = gm_crypto.sm4_encrypt_data(sensitive_data_str, sm4_key)
                                
                                # 构造加密响应
                                encrypted_response_data = {
                                    **classified['non_sensitive'],
                                    'encrypted_fields': encrypted_sensitive,
                                    'has_encryption': True
                                }
                            else:
                                # 无敏感数据，返回原响应
                                encrypted_response_data = response_data
                    else:
                        # 响应不是字典类型，返回原响应
                        encrypted_response_data = response_data
                        
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # JSON解析失败，返回原响应
                    encrypted_response_data = {
                        'code': 200,
                        'message': 'success',
                        'data': content_str
                    }
                except Exception as e:
                    # 处理过程中出错，记录日志并返回原响应
                    logger.error(f"敏感字段加密处理失败: {str(e)}", exc_info=True)
                    encrypted_response_data = {
                        'code': 200,
                        'message': 'success',
                        'data': content_str if isinstance(content, str) else content.decode('utf-8') if isinstance(content, bytes) else str(content)
                    }
                
                # 将加密后的数据转为JSON字符串
                encrypted_json = json.dumps(encrypted_response_data, ensure_ascii=False)
                
                # 创建新的响应对象
                from django.http import JsonResponse
                new_response = JsonResponse(
                    encrypted_response_data,
                    safe=False,
                    json_dumps_params={'ensure_ascii': False}
                )
                
                # 复制原响应的状态码和其他头部信息
                new_response.status_code = getattr(response, 'status_code', 200)
                
                # 复制重要的头部信息
                for header_name, header_value in response.items() if hasattr(response, 'items') else []:
                    # 跳过Content-Length，因为内容已经改变
                    if header_name.lower() != 'content-length':
                        new_response[header_name] = header_value
                
                
                return new_response
                
            except Exception as e:
                logger.error(f"响应加密失败: {str(e)}", exc_info=True)
                # 加密失败时返回原响应
                return response
        
        # 如果没有开启安全传输，直接返回原响应
        else:
            return response




