import 'dart:async';

import 'package:in_app_purchase/in_app_purchase.dart';
import 'package:in_app_purchase_android/in_app_purchase_android.dart';

import 'api.dart';
import 'estado.dart';

/// Google Play Billing. La compra va atada a la cuenta (obfuscatedAccountId = id_compra que da
/// el backend), el backend la verifica contra Google y la acredita, y recién entonces la app la
/// consume para que se pueda volver a comprar. Sin sesión no se compra.
class Compras {
  Compras(this.estado);

  final Estado estado;
  InAppPurchase get _iap => InAppPurchase.instance;
  StreamSubscription<List<PurchaseDetails>>? _escucha;
  Completer<void>? _enCurso;

  /// Escucha desde el arranque: una compra que quedó sin acreditar (la app se cerró a medias)
  /// se acredita al volver, con la sesión de la cuenta que la hizo.
  void iniciar() {
    _escucha ??= _iap.purchaseStream.listen(_procesar, onError: (Object e) => _enCurso?.completeError(e));
  }

  void cerrar() => _escucha?.cancel();

  Future<void> comprar() async {
    final cuenta = estado.cuenta;
    if (cuenta == null) throw ErrorApi('Entra a tu cuenta para continuar.');
    if (!await _iap.isAvailable()) throw ErrorApi('Google Play no está disponible en este dispositivo.');
    final producto = '${estado.config['producto'] ?? 'consultas_200'}';
    final r = await _iap.queryProductDetails({producto});
    if (r.productDetails.isEmpty) throw ErrorApi('Por ahora no se puede completar la compra. Vuelve a intentar más tarde.');
    _enCurso = Completer<void>();
    await _iap.buyConsumable(
      purchaseParam: PurchaseParam(productDetails: r.productDetails.first, applicationUserName: '${cuenta['id_compra']}'),
      autoConsume: false, // se consume después de que el backend la acredite
    );
    return _enCurso!.future;
  }

  Future<void> _procesar(List<PurchaseDetails> compras) async {
    for (final c in compras) {
      switch (c.status) {
        case PurchaseStatus.pending:
          continue;
        case PurchaseStatus.canceled:
          _enCurso?.complete();
        case PurchaseStatus.error:
          _enCurso?.completeError(ErrorApi('La compra no se completó.'));
        case PurchaseStatus.purchased || PurchaseStatus.restored:
          if (estado.cuenta == null) continue; // se acredita cuando la cuenta vuelva a entrar
          try {
            await estado.api.post('/cuenta/compra', {'token_compra': c.verificationData.serverVerificationData, 'producto': c.productID});
            final android = _iap.getPlatformAddition<InAppPurchaseAndroidPlatformAddition>();
            await android.consumePurchase(c);
            if (c.pendingCompletePurchase) await _iap.completePurchase(c);
            await estado.refrescarCuenta();
            _enCurso?.complete();
          } on ErrorApi catch (e) {
            _enCurso?.completeError(e);
          }
      }
      _enCurso = (_enCurso?.isCompleted ?? true) ? null : _enCurso;
    }
  }
}
